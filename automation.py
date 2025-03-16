import yaml
import re
import logging
import os
import time
import pyautogui  
import constants

# Disable failsafe
pyautogui.FAILSAFE = False

class Automation:
    """
    Class for handling YAML configuration operations automation.
    """
    
    def __init__(self, img_path=None, debug_path=None, config_path=None):
        """
        Initialize the Automation class
        
        Args:
            img_path: Path to the image directory
            debug_path: Path to the debug directory
            config_path: Path to the YAML configuration file (optional)
        """
        self.config = None
        self.img_path = img_path
        self.debug_path = debug_path
        
        # Load configuration if config_path is provided
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, file_path):
        """
        Load and store the YAML configuration
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            The parsed YAML content as a dictionary
        """
        self.config = self.read_config(file_path)
        return self.config

    @staticmethod
    def str_to_bool(str):
        """Convert string representation of boolean to actual boolean."""
        if str.lower() == "true":
            return True
        elif str.lower() == "false":
            return False
        else:
            raise ValueError(f"Invalid boolean value: {str}")
    
    @staticmethod
    def read_config(file_path):
        """
        Read and parse a YAML configuration file
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            The parsed YAML content as a dictionary
        """
        try:
            with open(file_path, 'r') as file:
                config = yaml.safe_load(file)
                return config
        except Exception as e:
            logging.error(f"Error reading YAML file: {e}")
            return None
    
    @staticmethod
    def process_template_vars(text, variables):
        """
        Replace template variables in format {{VAR_NAME}} with their values
        
        Args:
            text: Text containing template variables
            variables: Dictionary of variables to replace
            
        Returns:
            Text with variables replaced
        """
        if not isinstance(text, str):
            return text
            
        # Find all template variables in the format {{VAR_NAME}}
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, text)
        
        result = text
        for var_name in matches:
            if var_name in variables:
                result = result.replace(f"{{{{{var_name}}}}}", str(variables[var_name]))
            else:
                logging.warning(f"Variable {var_name} not found in provided variables")
        
        return result
    
    @staticmethod
    def wrap(func, *args, **kwargs):
        """
        Wrapper function to catch exceptions
        """
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            # logging.error(f"Error executing function: {func} args: {args}, kwargs: {kwargs}: {e}")
            return None
    
    def execute_locate_image(self, locate_image, variables=None):
        """
        Execute a locate_image operation from YAML configuration
        
        Args:
            variables: Dictionary of variables to replace
            
        Returns:
            Result based on success or failure
        """
        if self.img_path is None:
            logging.error("Image path not set.")
            return False

        
        if variables is None:
            variables = {}
            
        image = locate_image.get('image')
        image_path = os.path.join(self.img_path, image)
        click = self.str_to_bool(locate_image.get('click', 'False'))
        iterate = locate_image.get('iterate', 1)
        until_found = self.str_to_bool(locate_image.get('until_found', 'True'))
        sleep_time = locate_image.get('sleep', 0)
        confidence = locate_image.get('confidence', 0.9)
        
        logging.debug(f"Attempting to locate image: {image}")
        
        success = False
        result = None
        for i in range(iterate):
            result = self.wrap(pyautogui.locateCenterOnScreen, image_path, confidence=confidence)

            if result is not None:
                # Check if click is required
                if click: 
                    x, y = result  
                    pyautogui.click(x, y)
                    logging.debug(f"Clicked at position {x}, {y}")

            if until_found:
                # default - exit  after first time found
                if result is not None:
                    success = True
                    break          
            else:
                # inverse - exit after first time NOT found
                if result is None:
                    success = True
                    break

            if i < iterate - 1 and sleep_time > 0:
                time.sleep(sleep_time)

        if success:
            # Handle on_success
            on_success = locate_image.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(on_success, variables)
            return True
        else:
            # Debug screenshot
            if logging.getLogger().level == logging.DEBUG and self.debug_path is not None and constants.TIME_FORMAT is not None:
                pyautogui.screenshot(os.path.join(self.debug_path, time.strftime(
                    constants.TIME_FORMAT) + "-" + image))
                    
            # Handle on_error or on_failure
            on_error = locate_image.get('on_failure')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    return self.execute_operation(on_error, variables)
            return False
    
    def execute_keyboard_input(self, keyboard_input, variables=None):
        """
        Execute a keyboard_input operation from YAML configuration
        
        Args:
            variables: Dictionary of variables to replace
            
        Returns:
            Result based on success or failure
        """
        
        if variables is None:
            variables = {}
            
        sequence = keyboard_input.get('sequence', [])
        
        success = False
        try:
            for action in sequence:
                if 'press' in action:
                    key = self.process_template_vars(action['press'], variables)
                    pyautogui.press(key)
                    logging.debug(f"Pressed key: '{key}'")
            
                elif 'write' in action:
                    text = self.process_template_vars(action['write'], variables)
                    interval = action.get('interval', 0.1)  # Default interval
                    pyautogui.write(text, interval=interval)
                    logging.debug(f"Wrote text: '{text}'")
                
                elif 'hotkey' in action:
                    # Handle hotkey which can be in various formats
                    hotkey_data = action['hotkey']
                    
                    # Convert the hotkey data to a list of keys
                    if isinstance(hotkey_data, list):
                        keys = [self.process_template_vars(k, variables) for k in hotkey_data]
                    else:
                        # It's a string that needs parsing
                        hotkey_str = self.process_template_vars(hotkey_data, variables)
                        
                        # Clean up the string to extract keys (handles format like "['ctrl', 'a']")
                        hotkey_str = hotkey_str.strip('[]')
                        keys = []
                        for k in hotkey_str.split(','):
                            # Clean up each key
                            clean_key = k.strip().strip('\'"')
                            if clean_key:  # Only add non-empty keys
                                keys.append(clean_key)
                    
                    # Execute the hotkey action
                    if keys:
                        pyautogui.hotkey(*keys)
                        logging.debug(f"Pressed hotkey: '{keys}'")
                
                elif 'sleep' in action:
                    sleep_time = float(action['sleep'])
                    time.sleep(sleep_time)
                    logging.debug(f"Slept for {sleep_time} seconds")

            success = True
        except Exception as e:
            logging.error(f"Error executing keyboard input: {e}", exc_info=True)
            success = False

        if success:
            # Handle on_success
            on_success = keyboard_input.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(on_success, variables)
            return True
        else:
            # Handle on_error or on_failure
            on_error = keyboard_input.get('on_failure')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    return self.execute_operation(on_error, variables)
            return False
    
    def execute_operation(self, operation, variables=None):
        """
        Execute a YAML operation based on its type
        
        Args:
            operation: Dictionary containing operation configuration
            variables: Dictionary of variables to replace
            
        Returns:
            Result based on success or failure
        """
        if variables is None:
            variables = {}
            
        # Identify the operation type
        if 'locate_image' in operation:
            return self.execute_locate_image( operation.get('locate_image'), variables)
        elif 'keyboard_input' in operation:
            return self.execute_keyboard_input( operation.get('keyboard_input'), variables)
        else:
            # For nested operations, try to process each key
            for key, value in operation.items():
                if isinstance(value, dict):
                    result = self.execute_operation({key: value}, variables)
                    # If result is False, stop processing
                    if result is False:
                        return False
            return True
    
    def execute_instruction(self, instruction_name, variables=None):
        """
        Execute a list of instructions from the YAML configuration
        
        Args:
            instruction_name: Name of instruction to execute
            variables: Dictionary of variables to replace
            
        Returns:
            True if all instructions executed successfully, False otherwise
        """
        if self.config is None:
            logging.error("Configuration not loaded. Call load_config first.")
            return False
            
        if variables is None:
            variables = {}
        
        if instruction_name not in self.config:
            logging.error(f"Instruction: '{instruction_name}' not found in configuration")
            return False

        logging.debug(f"Start executing instruction: '{instruction_name}'")
        
        instruction_list = self.config[instruction_name]
        
        # If instruction_list is a list, process each item
        if isinstance(instruction_list, list):
            for instruction_item in instruction_list:
                for operation_name, operation in instruction_item.items():
                    logging.debug(f"Executing operation: '{operation_name}'")
                    result = self.execute_operation({operation_name: operation}, variables)
                    
                    # If an operation returns False, stop processing
                    if result is False:
                        logging.warning(f"Operation: '{operation_name} 'returned False, stopping execution")
                        break
        
        # If it's a dictionary, just execute it
        elif isinstance(instruction_list, dict):
            result = self.execute_operation(instruction_list, variables)
        
        logging.debug(f"Finished executing instruction: '{instruction_name}' with result: {result}")
        return result