# Temporal workflow for periodic cleanup of expired access records
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import os
from typing import Optional

# Import constants needed by activities (outside sandbox)
from shared.constants import SFTP_DATA_MOUNT_PATH, SFTP_RECORDINGS_DIR

# Import with sandbox passthrough for modules that use http.client and other restricted modules
with workflow.unsafe.imports_passed_through():
    from shared.access_api import AccessAPI
    from shared.access import AccessField, AccessType
    from shared.users_api import UserAPI
    from shared.users import UserField
    from shared.utilities import start_logging, start_debug
    from shared.constants import LOG_PERIODIC_MAINTENANCE, DEBUG_MODULE_PERIODIC_MAINTENANCE

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_USERNAME = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD')
SERVER_URL = os.getenv('SERVER_URL')
BASE_PATH = os.getenv('ZOOMREC_HOME')
if BASE_PATH is None:
    raise ValueError("ZOOMREC_HOME environment variable is not set")

# Temporal client (initialized on first use)
_temporal_client = None

start_logging(LOG_PERIODIC_MAINTENANCE)
start_debug(DEBUG_MODULE_PERIODIC_MAINTENANCE, os.getenv('DEBUG_PORT_SERVER'))

def get_context_prefix() -> str:
    """Return a standardized log prefix with workflow and/or activity context."""
    parts = []

    try:
        wf_info = workflow.info()
        parts.append(f"Workflow:'{wf_info.workflow_id}' Run:'{wf_info.run_id}'")
    except Exception:
        pass

    try:
        act_info = activity.info()
        parts.append(f"Activity:'{act_info.activity_type}'")
    except Exception:
        pass

    if parts:
        return f"({' '.join(parts)})"
    return "[NoContext]"

@dataclass
class QueryExpiredAccessInput:
    pass

@activity.defn
async def queryExpiredAccess(input: QueryExpiredAccessInput) -> list:
    """Query for expired access records that have delete_on_expire enabled.

    Returns:
        list: List of expired access records
    """
    try:
        with AccessAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as access_api:
            # Query for expired HTTP server access records with delete_on_expire enabled
            now = datetime.now()
            expired_access = access_api.get(filters=[
                [AccessField.ACCESS_TYPE.value, '=', AccessType.HTTP_SERVER_ACCESS.value],
                [AccessField.DELETE_ON_EXPIRE.value, '=', 1],  # 1 for true in database
                [AccessField.EXPIRES_AT.value, '<', now.isoformat()]
            ])

            logging.info(f"{get_context_prefix()} Found {len(expired_access)} expired access records with delete_on_expire enabled")
            return expired_access
    except Exception as e:
        logging.error(f"{get_context_prefix()} Failed to query expired access: {str(e)}")
        raise

@dataclass
class DeleteSftpFileInput:
    resource: str
    user_key: str

@activity.defn
async def deleteSftpFile(input: DeleteSftpFileInput) -> bool:
    """Delete a resource file from SFTP storage using direct filesystem access.
    
    Args:
        input: DeleteSftpFileInput containing resource and user_key
        
    Returns:
        bool: True if deletion was successful
    """
    try:
        # Get user login to determine the correct directory
        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            user = user_api.get(filters=[[UserField.KEY.value, "=", input.user_key]])[0]
            user_login = user[UserField.LOGIN.value]
        
        # Build the file path using BASE_PATH + SFTP_DATA_MOUNT_PATH like server app
        target_dir = os.path.join(BASE_PATH, SFTP_DATA_MOUNT_PATH, user_login, SFTP_RECORDINGS_DIR)
        
        # Find all files matching the resource pattern
        import glob
        file_pattern = os.path.join(target_dir, f"{input.resource}*")
        logging.debug(f"{get_context_prefix()} Looking for files matching pattern: {file_pattern}")
        logging.debug(f"{get_context_prefix()} Target directory exists: {os.path.exists(target_dir)}")
        if os.path.exists(target_dir):
            logging.debug(f"{get_context_prefix()} Contents of {target_dir}: {os.listdir(target_dir)}")
        files_to_delete = glob.glob(file_pattern)
        logging.debug(f"{get_context_prefix()} Found {len(files_to_delete)} files to delete: {files_to_delete}")
        
        if not files_to_delete:
            logging.warning(f"{get_context_prefix()} No files found matching pattern: {file_pattern}")
            return True  # No files to delete is considered success
        
        # Delete each file
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                logging.debug(f"{get_context_prefix()} Deleted file: {file_path}")
                deleted_count += 1
            except OSError as e:
                logging.error(f"{get_context_prefix()} Failed to delete file {file_path}: {str(e)}")
        
        logging.debug(f"{get_context_prefix()} Successfully deleted {deleted_count}/{len(files_to_delete)} files for resource {input.resource}")
        return deleted_count == len(files_to_delete)
    except Exception as e:
        logging.error(f"{get_context_prefix()} Failed to delete SFTP file: {str(e)}")
        raise

@dataclass
class DeleteAccessRecordInput:
    resource: str
    access_key: str
    access_type: int

@activity.defn
async def deleteAccessRecord(input: DeleteAccessRecordInput) -> bool:
    """Delete an access record from the database.
    
    Args:
        input: DeleteAccessRecordInput containing resource, access_key, and access_type
        
    Returns:
        bool: True if deletion was successful
    """
    try:
        with AccessAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as access_api:
            access_api.delete(
                resource=input.resource,
                access_key=input.access_key,
                access_type=input.access_type
            )
            logging.info(f"{get_context_prefix()} Successfully deleted access record for {input.resource}")
            return True
    except Exception as e:
        logging.error(f"{get_context_prefix()} Failed to delete access record: {str(e)}")
        raise

@dataclass
class AccessCleanupWorkflowInput:
    pass

@workflow.defn
class AccessCleanupWorkflow:
    @workflow.run
    async def run(self, input: AccessCleanupWorkflowInput):
        """Run the access cleanup workflow."""
        logging.info(f"{get_context_prefix()} Starting access cleanup workflow")
        
        # Query for expired access records
        expired_access = await workflow.execute_activity(
            queryExpiredAccess,
            QueryExpiredAccessInput(),
            start_to_close_timeout=timedelta(minutes=10),
            summary="Query expired access records"
        )
        
        if not expired_access:
            logging.info(f"{get_context_prefix()} No expired access records to clean up")
            return
        
        # Process each expired access record
        deleted_count = 0
        for access in expired_access:
            resource = access[AccessField.RESOURCE.value]
            access_key = access[AccessField.ACCESS_KEY.value]
            access_type = access[AccessField.ACCESS_TYPE.value]
            user_key = access[AccessField.USER_KEY.value]
            
            logging.info(f"{get_context_prefix()} Processing expired access for resource: {resource}")
            
            # Delete file from SFTP
            try:
                file_deleted = await workflow.execute_activity(
                    deleteSftpFile,
                    DeleteSftpFileInput(resource=resource, user_key=user_key),
                    start_to_close_timeout=timedelta(minutes=5),
                    summary=f"Delete SFTP file for {resource}"
                )
            except Exception as e:
                logging.error(f"{get_context_prefix()} Failed to delete SFTP file for {resource}: {str(e)}")
                file_deleted = False
            
            # Delete access record from database
            try:
                await workflow.execute_activity(
                    deleteAccessRecord,
                    DeleteAccessRecordInput(
                        resource=resource,
                        access_key=access_key,
                        access_type=access_type
                    ),
                    start_to_close_timeout=timedelta(minutes=5),
                    summary=f"Delete access record for {resource}"
                )
                deleted_count += 1
            except Exception as e:
                logging.error(f"{get_context_prefix()} Failed to delete access record for {resource}: {str(e)}")
        
        logging.info(f"{get_context_prefix()} Access cleanup completed. Deleted {deleted_count} access records")

async def get_temporal_client():
    """Get or create a shared Temporal client connection."""
    global _temporal_client
    
    if _temporal_client is None:
        TEMPORAL_SERVER = os.getenv('TEMPORAL_SERVER', 'localhost:7233')
        logging.info(f"Creating Temporal client connection to {TEMPORAL_SERVER}")
        _temporal_client = await Client.connect(TEMPORAL_SERVER)
        logging.info("Temporal client connected")
    
    return _temporal_client

async def scheduleAccessCleanup():
    """Schedule the periodic access cleanup workflow to run daily.
    
    This function creates a Temporal Schedule for the AccessCleanupWorkflow.
    It reuses a shared Temporal client connection.
    
    Returns:
        Schedule handle for the scheduled workflow
    """
    from temporalio.client import Schedule, ScheduleActionStartWorkflow, ScheduleSpec, ScheduleAlreadyRunningError
    from shared.constants import DEFAULT_PERIODIC_MAINTENANCE_CRON, PERIODIC_MAINTENANCE_CRON
    
    # Get shared Temporal client
    client = await get_temporal_client()
    
    CRON_SCHEDULE = os.getenv(PERIODIC_MAINTENANCE_CRON, DEFAULT_PERIODIC_MAINTENANCE_CRON)
    schedule_id = "zoomrec-access-cleanup-periodic"
    
    try:
        # Create a schedule with cron spec
        handle = await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    AccessCleanupWorkflow.run,
                    AccessCleanupWorkflowInput(),  # Input for workflow
                    id=schedule_id,
                    task_queue="access-cleanup-task-queue",
                ),
                spec=ScheduleSpec(
                    cron_expressions=[CRON_SCHEDULE],
                ),
            ),
        )
        
        logging.info(f"Successfully scheduled periodic access cleanup workflow with ID: {schedule_id}")
        logging.info(f"Workflow will run with cron schedule: {CRON_SCHEDULE}")
        logging.info(f"Handle: {handle.id}")
        return handle
        
    except ScheduleAlreadyRunningError:
        logging.info(f"Schedule '{schedule_id}' already exists, using existing schedule")
        handle = client.get_schedule_handle(schedule_id)
        return handle
    except Exception as e:
        logging.error(f"Failed to schedule periodic cleanup workflow: {e}")
        raise

async def main():
    """Main function to start the Temporal worker for access cleanup."""
    
    # Schedule the periodic access cleanup workflow
    handle = await scheduleAccessCleanup()
    logging.info(f"Started schedule cleanup with workflow id: '{handle.id}'")
    
    client = await get_temporal_client()
    
    logging.info("Connected to Temporal server")

    worker = Worker(
        client,
        task_queue="access-cleanup-task-queue",
        workflows=[AccessCleanupWorkflow],
        activities=[
            queryExpiredAccess,
            deleteSftpFile,
            deleteAccessRecord
        ]
    )
    
    logging.info("Starting Temporal worker for access cleanup...")
    
    await worker.run()

if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Access cleanup worker stopped by user")
    except Exception as e:
        logging.error(f"Error running access cleanup worker: {e}")
        raise
