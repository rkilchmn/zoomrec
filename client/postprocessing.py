# temporalio for postprocessing workflow
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
# type: ignore  # Pylance may not recognize these imports, but they are valid in temporalio
# from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions
from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess
import logging
import os
from typing import Optional
import secrets

# Import with sandbox passthrough for modules that use http.client and other restricted modules
with workflow.unsafe.imports_passed_through():
    from shared.events import (
        Events, EventField, EventStatus, EventInstructionAttribute, EventInstructionPostprocess,
        INSTRUCTION_UPLOAD_KEY_DELETE, INSTRUCTION_ACCESS_HTTP_SERVER,
        INSTRUCTION_ACCESS_KEY, INSTRUCTION_ACCESS_EXPIRE_AFTER_SECONDS,
        INSTRUCTION_ACCESS_NOTIFY_USER, INSTRUCTION_ACCESS_ADDITIONAL_EMAILS
    )
    from shared.events_api import EventAPI
    from shared.users import UserField
    from shared.users_api import UserAPI
    from shared.access_api import AccessAPI, EXPIRE_AFTER_SECONDS
    from shared.access import AccessField, AccessType
    from shared.utilities import start_logging, start_debug
    from shared.constants import DATETIME_FORMAT, VIDEO_EXTENSION, DEBUG_MODULE_POSTPROCESS, LOG_POSTPROCESS_FILENAME, SFTP_ADMIN_USERNAME, SFTP_ADMIN_USER_IDENTITY_FILE, SFTP_RECORDINGS_DIR, RECORDINGS_DIR, ROUTE_LIST


start_logging(LOG_POSTPROCESS_FILENAME)
start_debug(DEBUG_MODULE_POSTPROCESS, os.getenv('DEBUG_PORT_CLIENT'))

def get_context_prefix() -> str:
    """Return a standardized log prefix with workflow and/or activity context.

    Works in both workflow and activity execution contexts.
    Example output:
      [Workflow: 'zoomrec-client-postprocess' Run: '1234abcd' Activity: 'postprocess_activity']
    """
    parts = []

    # Check if inside workflow
    try:
        wf_info = workflow.info()
        parts.append(f"Workflow:'{wf_info.workflow_id}' Run:'{wf_info.run_id}'")
    except Exception:
        pass  # Not in workflow context

    # Check if inside activity
    try:
        act_info = activity.info()
        parts.append(f"Workflow:'{act_info.workflow_id}' Activity:'{act_info.activity_type}' Run:'{act_info.workflow_run_id}' Activity: '{act_info.activity_type}'")
    except Exception:
        pass  # Not in activity context

    # Return formatted prefix
    if parts:
        return f"({' '.join(parts)})"
    return "[NoContext]"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_USERNAME = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD')
SERVER_URL = os.getenv('SERVER_URL')
SSH_SERVER_URL = os.getenv('SSH_SERVER_URL')
BASE_PATH = os.getenv('ZOOMREC_HOME')
if BASE_PATH is None:
    raise ValueError("ZOOMREC_HOME environment variable is not set")
REC_PATH = os.path.join(BASE_PATH, RECORDINGS_DIR)

# Temporal client (initialized on first use)
_temporal_client = None


# Define desired postprocess execution order
def postprocess_order(step):
    EXECUTION_ORDER = [
        EventInstructionPostprocess.TRANSCRIBE.value,
        EventInstructionPostprocess.TRANSLATE.value,
        EventInstructionPostprocess.CUSTOM.value,
        EventInstructionPostprocess.UPLOAD.value,
        EventInstructionPostprocess.ACCESS.value,
    ]

    if not isinstance(step, dict):
        return len(EXECUTION_ORDER)
    for idx, key in enumerate(EXECUTION_ORDER):
        if key in step:
            return idx
    return len(EXECUTION_ORDER)

@dataclass
class UpdateStatusInput:
    event: dict
    client_id : str
    new_status: int

@activity.defn
async def updateStatus(input: UpdateStatusInput):
    with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
        # Get current event status
        try:
            current_event = event_api.get(filters=[[EventField.KEY.value, "=", input.event[EventField.KEY.value]]])[0]

        except Exception as e:
            logging.warning(f"{get_context_prefix()} Failed to retrieve event '{Events.nameStr(input.event)}'. This can happen if was deleted when postprocessing took too long")
            return  

        # Update event status and assignment info
        input.event[EventField.STATUS.value] = input.new_status
        
        if input.client_id:
            input.event[EventField.ASSIGNED.value] = input.client_id
            input.event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(input.event).isoformat()
        else:
            input.event[EventField.ASSIGNED.value] = ""
            input.event[EventField.ASSIGNED_TIMESTAMP.value] = ""
    
        # Save changes
        event_api.update(input.event)
        logging.info(f"{get_context_prefix()} Successfully updated event status to '{EventStatus.get_description(input.new_status)}'")

@dataclass
class consolidateRecordingInput:
    recording_basename_path: str

@activity.defn
async def consolidateRecording(input: consolidateRecordingInput) -> Optional[str]:
    # Consolidate videos if multiple recordings of same meeting
    command = f"{SCRIPT_DIR}/concatenate_video.sh '{input.recording_basename_path}' {VIDEO_EXTENSION} yes"
    logging.debug(f"{get_context_prefix()} Consolidate video command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"{get_context_prefix()} Error consolidating video: {result.stderr}")
        return None
    else:
        logging.debug(f"{get_context_prefix()} Consolidated video: {result.stdout}")
        return f"{input.recording_basename_path}.{VIDEO_EXTENSION}"

@dataclass
class getUserLoginInput:
    user_key: str

@activity.defn
async def getUserLogin(input: getUserLoginInput)->str:
    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
        user = user_api.get(filters=[[UserField.KEY.value, "=", input.user_key]])[0]
        return user[UserField.LOGIN.value]

@dataclass
class ProvideAccessInput:
    event: dict
    access_config: dict
    resource: str
    user_key: str
    
@activity.defn
async def provideAccess(input: ProvideAccessInput) -> dict:
    """Create HTTP server access for the recording.
    
    Args:
        input: ProvideAccessInput containing event, access config, resource, and user_key
        
    Returns:
        dict: Result of the access creation
    """
    try:
        with AccessAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as access_api:
            # Extract optional parameters
            expire_after_seconds = None
            if INSTRUCTION_ACCESS_EXPIRE_AFTER_SECONDS in input.access_config:
                expire_after_seconds = input.access_config[INSTRUCTION_ACCESS_EXPIRE_AFTER_SECONDS]
            
            notify_user = input.access_config.get(INSTRUCTION_ACCESS_NOTIFY_USER)
            additional_emails = input.access_config.get(INSTRUCTION_ACCESS_ADDITIONAL_EMAILS)
            if additional_emails:
                additional_emails = [email.strip() for email in additional_emails.split(',')]

            access_key = input.access_config.get(INSTRUCTION_ACCESS_KEY)
            if access_key is None:
                # generate random access key
                access_key = secrets.token_hex(16)

            access = access_api.create({
                AccessField.USER_KEY.value: input.user_key,
                AccessField.RESOURCE.value: input.resource,
                AccessField.ACCESS_KEY.value: access_key,
                AccessField.ACCESS_TYPE.value: AccessType.HTTP_SERVER_ACCESS.value,
                AccessField.NOTIFY_USER.value: notify_user,
                AccessField.ADDITIONAL_EMAILS.value: additional_emails
            }, expire_after_seconds=expire_after_seconds)
            logging.info(f"{get_context_prefix()} Successfully created HTTP access for {input.resource}")
            return access
    except Exception as e:
        logging.error(f"{get_context_prefix()} Failed to create HTTP access: {str(e)}")
        raise

@dataclass
class executePostprocessStepInput:
    event: dict
    step: str
    command: str
    filename_postprocess : str
    
@activity.defn
async def executePostprocessStep(input: executePostprocessStepInput):
    postprocessing_step_start = Events.now(input.event)
    logging.info(f"{get_context_prefix()} Started postprocessing step '{input.step}' at {postprocessing_step_start.strftime(DATETIME_FORMAT)}")

    logging.debug(f"{get_context_prefix()} Postprocessing step '{input.step}' command: {input.command}")
    postprocess_proc = subprocess.Popen(
        input.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
    if postprocess_proc:
        stdout, stderr = postprocess_proc.communicate()
        if postprocess_proc.returncode == 0:
            postprocessing_step_end = Events.now(input.event)
            postprocessing_step_duration = postprocessing_step_end - postprocessing_step_start
            logging.info(f"{get_context_prefix()} Postprocessing step '{input.step}' completed successfully at {postprocessing_step_end.strftime(DATETIME_FORMAT)} after {str(postprocessing_step_duration).split('.')[0]}")
        else:
            txt = f"Postprocessing step '{input.step}' failed with return code: {postprocess_proc.returncode} and error: {stderr.decode().strip()}"
            logging.error(f"{get_context_prefix()} {txt}")
            raise RuntimeError(txt)
        # debug output
        logging.debug(f"{get_context_prefix()} Postprocessing step '{input.step}' stdout: {stdout.decode().strip()}")
        logging.debug(f"{get_context_prefix()} Postprocessing step '{input.step}' stderr: {stderr.decode().strip()}")
    else:
        logging.error(f"{get_context_prefix()} Postprocessing step '{input.step}' failed to start.")
        raise RuntimeError(f"Postprocessing step '{input.step}' failed to start.")

@dataclass
class PostprocessWorkflowInput:
    recording_basename: str
    event: dict
    client_id: str
    postprocess_sorted: list
    
@workflow.defn
class PostprocessWorkflow:
    def __init__(self):
        self.skipped_tasks = set()

    @workflow.signal(name="skipSteps")
    def skip_steps_signal(self, task_names) -> None:
        """Signal handler to skip specific postprocessing steps.
        
        Args:
            task_names: A single task name (str) or list of task names to skip
        """
        if isinstance(task_names, str):
            task_names = [task_names]
        self.skipped_tasks.update(task_names)
        logging.info(f"{get_context_prefix()} Added tasks to skip: {', '.join(task_names)}")

    def should_skip_step(self, step_name: str) -> bool:
        """Check if the current step should be skipped.
        
        Args:
            step_name: Name of the step to check
            
        Returns:
            bool: True if the step should be skipped, False otherwise
        """
        if step_name in self.skipped_tasks:
            return True
        return False

    @workflow.run
    async def run(self, input: PostprocessWorkflowInput):
        workflow.upsert_search_attributes({"Event_Key": [input.event[EventField.KEY.value]]})
        workflow.upsert_search_attributes({"Event_Title": [input.event[EventField.TITLE.value]]})
        dtstart = datetime.strptime( input.event[EventField.DTSTART.value], DATETIME_FORMAT)
        dtstart = Events.replaceTimezone(dtstart, input.event[EventField.TIMEZONE.value])
        workflow.upsert_search_attributes({"Event_Start": [dtstart.isoformat()]})
        workflow.upsert_search_attributes({"Event_Start_Instance": [input.event['dtstart_instance']]})
        workflow.upsert_search_attributes({"Event_Filename": [input.recording_basename]})

        # set status to POSTPROCESS
        update_status_input = UpdateStatusInput(
                event=input.event,
                client_id=input.client_id,
                new_status=EventStatus.POSTPROCESS.value
            )
        await workflow.execute_activity(
            updateStatus,
            update_status_input,
            summary=f"Update Status to '{EventStatus.get_description(update_status_input.new_status)}'",
            start_to_close_timeout=timedelta(minutes=10)
        )

        # start postprocessing
        postprocessing_start = Events.now(input.event)
        logging.info(f"{get_context_prefix()} Started postprocessing for '{input.recording_basename}' at {postprocessing_start.strftime(DATETIME_FORMAT)}")

        # concatenate video
        filename_postprocess = await workflow.execute_activity(
            consolidateRecording,
            consolidateRecordingInput(
                recording_basename_path=f"{REC_PATH}/{input.recording_basename}"
            ),
            start_to_close_timeout=timedelta(hours=2),
            summary=f"Consolidate recording for '{input.recording_basename}'"
        )

        # Check if consolidation succeeded
        if not filename_postprocess:
            raise RuntimeError(f"Failed to consolidate recording for '{input.recording_basename}'. Aborting postprocessing.")

        # build postprocessing command
        for step in input.postprocess_sorted:
            command = None
            for key, value in step.items():
                match key:
                    case EventInstructionPostprocess.TRANSCRIBE.value:
                        command = f"{SCRIPT_DIR}/transcribe_video.sh {key} {filename_postprocess}"
                    case EventInstructionPostprocess.TRANSLATE.value:
                        command = f"{SCRIPT_DIR}/transcribe_video.sh {key}={value['language'] if 'language' in value else 'en'} {filename_postprocess}"
                    case EventInstructionPostprocess.UPLOAD.value:
                        if SSH_SERVER_URL:
                            user_login = await workflow.execute_activity(
                                getUserLogin,
                                getUserLoginInput(
                                    user_key=input.event[EventField.USER_KEY.value]
                                ),
                                summary=f"Get User login for User with key: '{input.event[EventField.USER_KEY.value]}'",
                                start_to_close_timeout=timedelta(minutes=10)
                            )
                            command = (
                                f"{SCRIPT_DIR}/sftp_upload.sh '{REC_PATH}/{input.recording_basename}' "
                                f"'{SFTP_ADMIN_USERNAME}@{SSH_SERVER_URL}' "
                                f"'{BASE_PATH}/{SFTP_ADMIN_USER_IDENTITY_FILE}' "
                                f"'{user_login}/{SFTP_RECORDINGS_DIR}' {value[INSTRUCTION_UPLOAD_KEY_DELETE] if INSTRUCTION_UPLOAD_KEY_DELETE in value else 'true'}"
                            )
                        else:
                            logging.error(f"{get_context_prefix()} SFTP transfer to server cannot be initiated: SSH_SERVER_URL not specified.")
                    case EventInstructionPostprocess.CUSTOM.value:
                        # Handle both single task (dict) and multiple tasks (list)
                        tasks = value if isinstance(value, list) else [value]
                        commands = []
                        
                        for task in tasks:
                            if not isinstance(task, dict) or 'task' not in task:
                                logging.error(f"{get_context_prefix()} Invalid custom task format: {task}")
                                continue
                            
                            # Build command for this task
                            script_name = task['task']
                            script_path = f"{SCRIPT_DIR}/{script_name}"
                            
                            # causes error: Cannot access os.path.isfile from inside a workflow
                            # # Check if script exists and is executable
                            # if not os.path.isfile(script_path) or not os.access(script_path, os.X_OK):
                            #     logging.error(f"Script not found or not executable: {script_path}")
                            #     continue
                            
                            # Build the command with the script and its arguments
                            cmd = f"{script_path} {filename_postprocess}"
                            for param, param_value in task.items():
                                if param != 'task':  # Skip task as it's used as script name
                                    cmd += f" --{param} '{param_value}'"  # Quote the parameter value
                            commands.append(cmd)
                        
                        # Join commands with && to run them sequentially
                        command = " && ".join(commands) if commands else ""

                    case EventInstructionPostprocess.ACCESS.value:
                        # Handle HTTP server access configuration
                        access_configs = step.get(EventInstructionPostprocess.ACCESS.value, [])
                        for access_config in access_configs:
                            if INSTRUCTION_ACCESS_HTTP_SERVER in access_config:
                                await workflow.execute_activity(
                                    provideAccess,
                                    ProvideAccessInput(
                                        event=input.event,
                                        access_config=access_config[INSTRUCTION_ACCESS_HTTP_SERVER],
                                        resource=input.recording_basename,
                                        user_key=input.event[EventField.USER_KEY.value]
                                    ),
                                    summary=f"Create HTTP access for resource: '{input.recording_basename}'",
                                    start_to_close_timeout=timedelta(minutes=5)
                                )
                    case _:
                        logging.error(f"{get_context_prefix()} Unknown postprocessing step: '{key}'")
                        continue
            if command:
                # Check if this step should be skipped
                if self.should_skip_step(key):
                    logging.info(f"{get_context_prefix()} Skipping execution of postprocessing step '{key}' as requested")
                    continue
                    
                await workflow.execute_activity(
                    executePostprocessStep,
                    executePostprocessStepInput(
                        event=input.event,
                        step=key,
                        command=command,
                        filename_postprocess=filename_postprocess,
                    ),
                    summary=f"Execute postprocessing step '{key}' for '{input.recording_basename}'",
                    start_to_close_timeout=timedelta(hours=4)
                )

        # set status to ENDED
        update_status_input = UpdateStatusInput(
                event=input.event,
                client_id=input.client_id,
                new_status=EventStatus.ENDED.value
            )
        await workflow.execute_activity(
            updateStatus,
            update_status_input,
            summary=f"Update Status to '{EventStatus.get_description(update_status_input.new_status)}'",
            start_to_close_timeout=timedelta(minutes=10)
        )

async def get_temporal_client():
    """Get or create a shared Temporal client connection.
    
    Returns:
        Temporal Client instance
    """
    global _temporal_client
    
    if _temporal_client is None:
        TEMPORAL_SERVER = os.getenv('TEMPORAL_SERVER', 'localhost:7233')
        logging.info(f"Creating Temporal client connection to {TEMPORAL_SERVER}")
        _temporal_client = await Client.connect(TEMPORAL_SERVER)
        logging.info("Temporal client connected")
    
    return _temporal_client


async def schedulePostprocess(postprocess, recording_basename, event, client_id):
    """Schedule a postprocessing workflow for a recording.
    
    This function reuses a shared Temporal client connection, allowing
    multiple calls without creating new connections each time.
    
    Args:
        postprocess: List of postprocessing instructions
        recording_basename: Base name of the recording file
        event: Event dictionary using EventField keys
        client_id: ID of the client scheduling the postprocess
        
    Returns:
        Workflow handle for the started workflow
    """
    # Get shared Temporal client
    client = await get_temporal_client()

    if isinstance(postprocess, list) and len(postprocess) > 0:
    
        # sequence postprocessing instruction
        postprocess_sorted = sorted(postprocess, key=postprocess_order)
        
        # Generate workflow ID based on event
        workflow_id = f"zoomrec-client-postprocess-{recording_basename}"
        
        # Start the workflow
        handle = await client.start_workflow(
            PostprocessWorkflow.run,
            PostprocessWorkflowInput(
                recording_basename=recording_basename,
                event=event,
                client_id=client_id,
                postprocess_sorted=postprocess_sorted
            ),
            id=workflow_id,
            task_queue="postprocess-task-queue",
        )
        
        logging.info(f"Scheduled posprocessing workflow id: '{workflow_id}' and handle: '{handle.id}'")
        return handle
    else:
        logging.error("No postprocessing instructions found for '{recording_basename}'")
        return None

async def main():
    """Main function to start the Temporal worker for postprocessing.
    
    This worker will listen for postprocessing workflow tasks and execute
    the registered activities (updateStatus, consolidateRecording, getUserLogin, executePostprocessStep).
    """
    
    # Get shared Temporal client
    client = await get_temporal_client()
    
    logging.info("Connected to Temporal server")

    worker = Worker(
        client,
        task_queue="postprocess-task-queue",
        workflows=[PostprocessWorkflow],
        activities=[
            updateStatus,
            consolidateRecording,
            getUserLogin,
            executePostprocessStep,
            provideAccess
        ]
    )
    
    logging.info("Starting Temporal worker for postprocessing...")
    
    # Run the worker
    await worker.run()


if __name__ == "__main__":
    """Entry point for running the postprocessing worker."""
    import asyncio
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Postprocessing worker stopped by user")
    except Exception as e:
        logging.error(f"Error running postprocessing worker: {e}")
        raise