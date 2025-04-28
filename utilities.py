import logging
import os
import constants
import traceback
import sys
import debugpy

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
        formatter = logging.Formatter(constants.LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # # Configure the logging
        # logging.basicConfig(filename=log_filepath, filemode="a", format=constants.LOG_FORMAT, level=LOG_LEVEL)
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