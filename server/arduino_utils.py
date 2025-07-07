from datetime import datetime
import os
import os.path
import glob
import re
from typing import Tuple, Optional, List, Union
from shared.constants import ARDUINO_CONFIG_EXTENSION, ARDUINO_FIRMWARE_EXTENSION

# Error codes for config file operations
ERROR_CONFIG_DIR_NOT_FOUND = "config_dir_not_found"
ERROR_CONFIG_DIR_READ = "config_dir_read_error"
ERROR_NO_COMPATIBLE_CONFIG = "no_compatible_config"
ERROR_NO_CONFIG_FILES = "no_config_files"
ERROR_NO_VALID_CONFIG_FILES = "no_valid_config_files"
ERROR_CONFIG_READ = "config_read_error"
ERROR_NO_NEWER_CONFIG = "no_newer_config"
ERROR_FIRMWARE_DIR_NOT_FOUND = "firmware_dir_not_found"
ERROR_NO_COMPATIBLE_FIRMWARE = "no_compatible_firmware"
ERROR_UNEXPECTED = "unexpected_error"

# Version string pattern: 'name.ino-Mon DD YYYY-HH:MM:SS' or 'name-Mon DD YYYY-HH:MM:SS'
VERSION_PATTERN = re.compile(
    r'^(.+?)(?:\.\w+)?-'  # Name part (with optional .ext)
    r'(\w{3}  \d{1,2} \d{4}-\d{1,2}:\d{2}:\d{2})'  # Date part
)

def parse_version_string(version_str: str) -> Tuple[str, datetime]:
    """
    Parse a version string into its components.
    
    Args:
        version_str: Version string in format 'name.ino-Mon DD YYYY-HH:MM:SS' or 'name-Mon DD YYYY-HH:MM:SS'
        
    Returns:
        Tuple of (base_name, version_datetime)
        
    Raises:
        ValueError: If the version string is not in the expected format
    """
    match = VERSION_PATTERN.match(version_str.strip())
    if not match:
        raise ValueError(f"Invalid version format. Expected 'name[-.ext]-Mon DD YYYY-HH:MM:SS'")
    
    name_part, date_part = match.groups()
    base_name = name_part.split('.')[0]  # Remove any extension
    
    try:
        # Parse the date part (format: 'Mon DD YYYY-HH:MM:SS')
        version_time = datetime.strptime(date_part, '%b %d %Y-%H:%M:%S')
        return base_name, version_time.replace(microsecond=0)
    except ValueError as e:
        raise ValueError(f"Invalid date format in version string: {date_part}") from e

# Alias for backward compatibility
parse_firmware_version = parse_version_string

def get_config_file_path(CONFIG_PATH: str, firmware_name: str, firmware_version: datetime, current_config_version: datetime) -> Tuple[Optional[str], Optional[dict]]:
    """
    Get the path to the most recent compatible config file for the given firmware.
    
    The function first finds the newest compatible config directory where the firmware version
    is greater than or equal to the directory version. Then, it looks for the newest config
    file in that directory and returns it if its version is newer than current_config_version.
    
    Args:
        CONFIG_PATH: Path to the directory containing config files
        firmware_name: The base name of the firmware (e.g., 'ESP8266_zoomrec')
        firmware_version: The firmware version as a datetime object
        current_config_version: The current config version as a datetime object
        
    Returns:
        Tuple of (config_file_path, error_dict) where:
        - config_file_path: Path to the config file if found, None otherwise
        - error_dict: Dictionary with 'error_code' and 'error_msg' if an error occurred, None if successful
    """
    if not os.path.isdir(CONFIG_PATH):
        return None, {"error_code": ERROR_CONFIG_DIR_NOT_FOUND, "error_msg": "Configuration directory not found"}
        
    # Stage 1: Find all compatible config directories (firmware_version >= dir_version)
    compatible_dirs = []
    try:
        for dir_name in os.listdir(CONFIG_PATH):
            dir_path = os.path.join(CONFIG_PATH, dir_name)
            if not os.path.isdir(dir_path) or not dir_name.startswith(firmware_name):
                continue
                
            try:
                # Parse version from directory name (format: name-{date})
                _, dir_version = parse_version_string(dir_name)
                if firmware_version >= dir_version:
                    compatible_dirs.append((dir_name, dir_version))
            except ValueError as e:
                continue
                
    except OSError as e:
        return None, {"error_code": ERROR_CONFIG_DIR_READ, "error_msg": f"Error reading config directory: {str(e)}"}
    
    if not compatible_dirs:
        return None, {"error_code": ERROR_NO_COMPATIBLE_CONFIG, "error_msg": f"No compatible config directories found for firmware version {firmware_version}"}
    
    # Get the newest compatible directory (highest version number)
    compatible_dirs.sort(key=lambda x: x[1], reverse=True)
    newest_dir, newest_dir_version = compatible_dirs[0]
      
    # Stage 2: Find the newest config file in the selected directory
    config_dir = os.path.join(CONFIG_PATH, newest_dir)
    try:
        config_files = [
            f for f in os.listdir(config_dir)
            if f.endswith(ARDUINO_CONFIG_EXTENSION) and os.path.isfile(os.path.join(config_dir, f))
        ]
        
        if not config_files:
            return None, {"error_code": ERROR_NO_CONFIG_FILES, "error_msg": f"No config files found in directory {newest_dir}"}
        
        # Find the newest config file based on version in filename
        newest_config = None
        newest_version = None
        
        for config_file in config_files:
            try:
                # Parse version from filename (format: name-{date}.json)
                base_name = config_file[:-len(ARDUINO_CONFIG_EXTENSION)]
                _, file_version = parse_version_string(base_name)
                
                if newest_version is None or file_version > newest_version:
                    newest_version = file_version
                    newest_config = config_file
                    
            except ValueError:
                continue
        
        if newest_config is None:
            return None, {"error_code": ERROR_NO_VALID_CONFIG_FILES, "error_msg": f"No valid config files found in directory {newest_dir}"}
        
        # Check if the config file is newer than current config version
        if newest_version > current_config_version:
            return os.path.join(config_dir, newest_config), None
        else:
            return None, {"error_code": ERROR_NO_NEWER_CONFIG, "error_msg": f"No newer config version available. Current: {current_config_version}, Latest: {newest_version}"}
            
    except OSError as e:
        return None, {"error_code": ERROR_CONFIG_READ, "error_msg": f"Error reading config directory {newest_dir}: {str(e)}"}
    
    except Exception as e:
        return None, {"error_code": ERROR_UNEXPECTED, "error_msg": f"Unexpected error: {str(e)}"}

def find_compatible_firmware(firmware_path: str, firmware_name: str, 
                           current_version_time: datetime) -> Tuple[Optional[str], Optional[dict]]:
    """
    Find the most recent compatible firmware file that is newer than the current version.
    
    Args:
        firmware_path: Path to the firmware directory
        firmware_name: Base name of the firmware (e.g., 'ESP8266_zoomrec')
        current_version_time: Datetime of the current firmware version
        
    Returns:
        Tuple of (filepath, error_dict) where:
        - filepath: Path to the firmware file if found, None otherwise
        - error_dict: Dictionary with 'error_code' and 'error_msg' if an error occurred, None if successful
    """
    if not os.path.isdir(firmware_path):
        return None, {"error_code": ERROR_FIRMWARE_DIR_NOT_FOUND, 
                    "error_msg": f"Firmware directory not found: {firmware_path}"}
    
    try:
        # Pattern to match firmware files: ESP8266_zoomrec.ino-*.ino.bin
        pattern = os.path.join(firmware_path, f"{firmware_name}.ino-*{ARDUINO_FIRMWARE_EXTENSION}")
        firmware_files = glob.glob(pattern)
        
        compatible_firmware = []
        
        for filepath in firmware_files:
            try:
                # Extract version from filename
                base_name = os.path.basename(filepath)
                version_str = base_name.replace(f"{firmware_name}.ino-", "").replace(ARDUINO_FIRMWARE_EXTENSION, "")
                
                # Parse the version datetime using our unified parser
                _, version_time = parse_version_string(f"{firmware_name}-{version_str}")
                
                # Only consider versions newer than current version
                if version_time > current_version_time:
                    compatible_firmware.append((filepath, version_time))
                    
            except ValueError:
                continue
        
        if not compatible_firmware:
            return None, {"error_code": ERROR_NO_COMPATIBLE_FIRMWARE,
                        "error_msg": f"No compatible firmware found newer than version {current_version_time}"}
            
        # Return the most recent firmware (sorted by version_time in descending order)
        compatible_firmware.sort(key=lambda x: x[1], reverse=True)
        return compatible_firmware[0], None
        
    except Exception as e:
        error_msg = f"Error searching for firmware: {str(e)}"
        return None, {"error_code": ERROR_UNEXPECTED,
                    "error_msg": error_msg}