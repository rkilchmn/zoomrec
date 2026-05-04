import logging
import os
import psutil
import re
import traceback
import sys
import debugpy
import signal
from datetime import datetime
from typing import Any, Dict, Optional, Match
from humanfriendly import parse_size

from . import constants
from .users_api import UserAPI
from .events import Events

# Pre-compile regex pattern for better performance
_TEMPLATE_PATTERN = re.compile(r'\{(?P<field>[a-zA-Z0-9_.]+)(?::(?P<format>[^}]*))?\}')
# Pattern to match {{CONSTANT_NAME}} placeholders
_CONSTANT_PLACEHOLDER_PATTERN = re.compile(r'\{\{([A-Z_]+)\}\}')

def replace_constant_placeholders(template_str: str) -> str:
    """
    Replace {{CONSTANT_NAME}} placeholders in a string with values from constants module.
    
    Args:
        template_str (str): The string containing {{CONSTANT_NAME}} placeholders
        
    Returns:
        str: The string with placeholders replaced by their constant values
        
    Example:
        >>> replace_constant_placeholders("Format: {{DATETIME_FORMAT}}")
        "Format: %d/%m/%Y %H:%M"
    """
    def replace_match(match: Match) -> str:
        constant_name = match.group(1)
        # Try to get the constant from the constants module
        if hasattr(constants, constant_name):
            value = getattr(constants, constant_name)
            return str(value)
        else:
            logging.warning(f"Constant '{constant_name}' not found in constants module. Keeping placeholder.")
            return match.group(0)  # Return original placeholder if not found
    
    return _CONSTANT_PLACEHOLDER_PATTERN.sub(replace_match, template_str)

def convert_to_safe_filename(filename):
    invalid_chars = '\\/:*?"\'<>|'
    safe_filename = ''.join(char for char in filename if char not in invalid_chars)
    safe_filename = safe_filename.strip()
    safe_filename = safe_filename.replace(' ', '_')
    if not safe_filename:
        safe_filename = '_'
    safe_filename = safe_filename[:255]
    return safe_filename

def create_unique_filename(directory_path, basename, extension):
    """
    Creates a unique filename by combining directory path, basename, and extension.
    If the file already exists, adds numerical suffixes (_1, _2, etc.) until a unique name is found.
    
    Args:
        directory_path (str): The directory path where the file will be saved
        basename (str): The base name of the file (without extension)
        extension (str): The file extension (with or without the dot)
    
    Returns:
        str: A unique full path filename
    """
    import os
    
    # Ensure extension starts with a dot
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    
    # Create the initial filename
    filename = os.path.join(directory_path, f"{basename}{extension}")
    
    # If the file doesn't exist, return the filename
    if not os.path.exists(filename):
        return filename
    
    # If the file exists, add numerical suffix
    counter = 1
    while True:
        new_filename = os.path.join(directory_path, f"{basename}_{counter}{extension}")
        if not os.path.exists(new_filename):
            return new_filename
        counter += 1

# Define a function to log uncaught exceptions using traceback
def exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)  # Allow Ctrl+C to exit normally
        return
    
    # Manually format the full traceback
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.error(f"Unhandled Exception:\n{error_message}")

class FlushFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

def start_logging( log_filename):
    sys.excepthook = exception_handler
    try:
        BASE_PATH = os.getenv('ZOOMREC_HOME')
        LOG_PATH = os.path.join(BASE_PATH, constants.LOG_DIR)
        log_filepath = os.path.join(LOG_PATH, log_filename)

        # Create the log file name with the timestamp
        LOG_LEVEL = getattr(logging, os.getenv( "LOG_LEVEL", "INFO"), logging.INFO)

        logger = logging.getLogger()
        logger.setLevel(LOG_LEVEL)

        # Remove default handlers (if re-running in interactive environments)
        logger.handlers.clear()

        handler = FlushFileHandler(log_filepath, mode="a")
        formatter = logging.Formatter(fmt=constants.LOG_FORMAT,datefmt=constants.DATETIME_FORMAT_LOG)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # # Configure the logging
        # logging.basicConfig(filename=log_filepath, filemode="a", format=constants.LOG_FORMAT, level=LOG_LEVEL)
        
        # Suppress verbose Temporal SDK debug messages (omit JSON payloads)
        logging.getLogger("temporalio").setLevel(logging.WARNING)
        
        logging.info(f"Starting logging {log_filename}")
        return True
    except Exception as e:
        print(f"Error start logging: {str(e)}")
        return False

def start_debug(debug_module, debug_port): 
    if os.getenv('DEBUG_MODULE','').lower().strip() == debug_module.lower() and debug_port:
        logging.info(f"Listening for debugger for module {debug_module} on port {debug_port}") 
        debugpy.listen(("0.0.0.0", int(debug_port)))
        print("Waiting for debugger attach")
        debugpy.wait_for_client()
        print("Debugger attached")
        logging.info(f"Debugger attached for module {debug_module} on port {debug_port}") 
        return True
    else:
        return False

def end_process(proc):
    if proc is not None:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc = None


def format_template(
    template: str,
    data: Dict[str, Any],
    default: str = '',
    datetime_format: str = '%Y-%m-%d %H:%M:%S'
) -> str:
    """
    Format a template string using dictionary values with support for datetime formatting.
    
    Args:
        template: The template string with {field} or {field:format} placeholders
        data: Dictionary containing the values to substitute
        default: Default value to use when a field is missing
        datetime_format: Default datetime format string
        
    Returns:
        Formatted string with placeholders replaced by values
        
    Examples:
        data = {
            'title': 'Team Meeting',
            'dtstart': '2023-09-25 14:30:00',
            'user': {'name': 'John', 'id': 42}
        }
        
        # Basic usage
        format_template("{title}_{dtstart:%Y%m%d}", data)  # "Team Meeting_20230925"
        
        # With nested fields
        format_template("User: {user.name} (ID: {user.id})", data)  # "User: John (ID: 42)"
        
        # Multiple datetime formats
        format_template("Meeting at {dtstart:%H:%M} on {dtstart:%Y-%m-%d}", data)  # "Meeting at 14:30 on 2023-09-25"
    """
    # Handle escaped braces
    if '{{' in template or '}}' in template:
        template = template.replace('{{', '\x00').replace('}}', '\x01')
    
    def get_value(field: str) -> Any:
        """Get value from data dictionary with support for nested fields."""
        value = data
        for part in field.split('.'):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value
    
    def replace_match(match: Match) -> str:
        field = match.group('field')
        fmt = match.group('format')
        value = get_value(field)
        
        if value is None:
            return default
            
        # Handle datetime formatting
        if fmt is not None:
            try:
                if isinstance(value, str):
                    value = datetime.strptime(value, datetime_format)
                if isinstance(value, (datetime, datetime.date)):
                    return value.strftime(fmt)
            except (ValueError, TypeError, AttributeError):
                pass
                
        return str(value)
    
    # Process the template
    result = _TEMPLATE_PATTERN.sub(replace_match, template)
    
    # Restore escaped braces if needed
    if '\x00' in result or '\x01' in result:
        result = result.replace('\x00', '{').replace('\x01', '}')

    return result

def notify_low_disk_space(user_key, check_path, min_disk_size, context, server_url, server_username, server_password):
    """Check free disk space and notify all admin users if below threshold.

    Args:
        user_key (str): User key for notification (kept for backward compatibility, now optional).
        check_path (str): Path to the directory to check.
        min_disk_size (str): Minimum free disk space as human-readable string (e.g. '5 GB').
        context (str): Context string for logging/notification (e.g. event name).
        server_url (str): Server URL for UserAPI.
        server_username (str): Server username for UserAPI.
        server_password (str): Server password for UserAPI.

    Returns:
        bool: True if low disk space was reported (notifications sent), False otherwise.

    Parses min_disk_size to bytes and checks if free space is below threshold.
    Notifies all admin users if disk space is below threshold.
    """
    try:
        min_free_space_bytes = parse_size(min_disk_size)
    except Exception:
        logging.error(f"Invalid min_disk_size value '{min_disk_size}'. Skipping disk space check.")
        return False

    try:
        disk_usage = psutil.disk_usage(check_path)
        if disk_usage.free < min_free_space_bytes:
            free_gb = disk_usage.free / (1024 ** 3)
            threshold_gb = min_free_space_bytes / (1024 ** 3)
            warning_msg = (
                f"⚠️ Low disk space: only {free_gb:.2f} GB free "
                f"(threshold: {threshold_gb:.2f} GB) on {check_path}. "
                f"{context}."
            )
            logging.warning(warning_msg)
            try:
                with UserAPI(server_url, server_username, server_password) as user_api:
                    # Query all admin users
                    from .users import UserField, UserRole
                    admin_users = user_api.get(filters=[[UserField.ROLE.value, "=", UserRole.ADMIN.value]])
                    
                    # Collect unique user keys to notify (admin users + user_key if provided)
                    notify_keys = set()
                    if admin_users:
                        for admin_user in admin_users:
                            admin_key = admin_user.get(UserField.KEY.value)
                            if admin_key:
                                notify_keys.add(admin_key)
                    
                    # Add user_key if provided (set ensures no duplicates)
                    if user_key:
                        notify_keys.add(user_key)
                    
                    if notify_keys:
                        for notify_key in notify_keys:
                            user_api.notify(
                                user_key=notify_key,
                                message=warning_msg,
                                subject="⚠️ Low Disk Space Warning"
                            )
                            # Find user name for logging
                            user_name = "unknown"
                            if admin_users:
                                for admin_user in admin_users:
                                    if admin_user.get(UserField.KEY.value) == notify_key:
                                        user_name = admin_user.get(UserField.NAME.value)
                                        break
                            if notify_key == user_key and user_name == "unknown":
                                user_name = user_key
                            logging.info(f"Sent low disk space notification to user: {user_name}")
                    else:
                        logging.warning("No users found to notify about low disk space")
                return True
            except Exception as e:
                logging.error(f"Error sending low disk space notification: {e}")
                return False
        else:
            logging.debug(f"Disk space check passed: {disk_usage.free / (1024 ** 3):.2f} GB free (threshold: {min_free_space_bytes / (1024 ** 3):.2f} GB)")
            return False
    except Exception as e:
        logging.error(f"Error checking disk space: {e}")
        return False
        