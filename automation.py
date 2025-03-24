import yaml
import re
import logging
import os
import time
import pyautogui  
import constants
import subprocess
import random
import constants
import traceback

# Disable failsafe
pyautogui.FAILSAFE = False

class Automation:
    """
    Class for handling YAML configuration operations automation.
    """
    
    def __init__(self, config_path=None, img_path=None, audio_path=None, debug_path=None):
        """
        Initialize the Automation class
        
        Args:
            img_path: Path to the image directory
            debug_path: Path to the debug directory
            config_path: Path to the YAML configuration file (optional)
            audio_path: Path to the audio directory (optional)
        """
        self.config = None
        self.img_path = img_path
        self.debug_path = debug_path
        self.audio_path = audio_path
        
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
    
    def execute_locate_image(self, breadcrumbs, locate_image, variables=None):

        if variables is None:
            variables = {}
                
        image = locate_image.get('image')
        image_path = os.path.join(self.img_path, image)
        click = self.str_to_bool(locate_image.get('click', 'False'))
        iterate = locate_image.get('iterate', 1)
        until_found = self.str_to_bool(locate_image.get('until_found', 'True'))
        sleep_time = locate_image.get('sleep', 0)
        confidence = locate_image.get('confidence', 0.9)
        minSearchTime = locate_image.get('minSearchTime', 0)

        breadcrumbs += f"/LocateImage:[{image}]"
        logging.debug(f"{breadcrumbs}")

        success = False
        if self.img_path is None:
            logging.error("Image path not set.")
        else:
            for i in range(iterate):
                result = self.wrap(pyautogui.locateCenterOnScreen, image_path, confidence=confidence, minSearchTime=minSearchTime)

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

        logging.debug(f"Image: {image} result after {i+1} of {iterate} iterations: {result} success: {success}")

        if success:
            # Handle on_success
            on_success = locate_image.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Debug screenshot
            if logging.getLogger().level == logging.DEBUG and self.debug_path is not None:
                pyautogui.screenshot(os.path.join(self.debug_path, time.strftime(
                    constants.TIME_FORMAT_LOG) + "-" + image))
                    
            # Handle on_error or on_error
            on_error = locate_image.get('on_error')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
    
    def execute_keyboard_input(self, breadcrumbs, keyboard_input, variables=None):

        if variables is None:
            variables = {}
            
        sequence = keyboard_input.get('sequence', [])

        breadcrumbs += f"/KeyboardInput[{len(sequence)}]"
        logging.debug(f"{breadcrumbs}")
        
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

        logging.debug(f"Keyboard input with sequence of {len(sequence)} keys executed with success: {success}") 

        if success:
            # Handle on_success
            on_success = keyboard_input.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error or on_error
            on_error = keyboard_input.get('on_error')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
    
    def execute_play_audio(self, breadcrumbs, play_audio, variables=None):
        try:
            # Check if specific audio file is specified
            specific_audio = play_audio.get('audio')

            breadcrumbs += f"/PlayAudio:[{specific_audio}]"
            logging.debug(f"{breadcrumbs}")
            
            if self.audio_path is None:
                logging.error("Audio path not set.")
                success = False
            else:
                if specific_audio:
                    # Play specific audio file
                    audio_file_path = os.path.join(self.audio_path, specific_audio)
                    if not os.path.exists(audio_file_path):
                        logging.error(f"Audio file not found: {audio_file_path}")
                        audio_file_path = None
                else:
                    # Get all files in audio directory
                    files = os.listdir(self.audio_path)
                    # Filter .wav files
                    files = list(filter(lambda f: f.endswith(".wav"), files))
                    # Check if .wav files available
                    if len(files) > 0:
                        # Get random file
                        file = random.choice(files)
                        audio_file_path = os.path.join(self.audio_path, file)
                    else:
                        logging.error("No .wav files found!")
                        audio_file_path = None

                if audio_file_path is not None:   
                    # Use paplay to play .wav file on specific Output
                    command = "/usr/bin/paplay --device=microphone -p " + audio_file_path
                    play = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    res, err = play.communicate()
                    success = play.returncode == 0

        except Exception as e:
            logging.error(f"Error executing play_audio: {e}", exc_info=True)
            success = False

        logging.debug(f"Audio: {audio_file_path} played with result: {success}")
        
        if success:
            # Handle on_success
            on_success = play_audio.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error
            on_error = play_audio.get('on_error')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
                
    def execute_set_variable(self, breadcrumbs, set_variable, variables=None):
        """
        Execute a set_variable operation
        
        Args:
            breadcrumbs: String tracking execution path
            set_variable: Dictionary containing set_variable configuration
            variables: Dictionary of variables to update
            
        Returns:
            Result based on success or failure
        """
        if variables is None:
            variables = {}
        
        variable_name = set_variable.get('variable')
        value = set_variable.get('value')
        
        # Process template variables in value if it's a string
        if isinstance(value, str):
            value = self.process_template_vars(value, variables)
        
        breadcrumbs += f"/SetVariable:[{variable_name}={value}]"
        logging.debug(f"{breadcrumbs}")
        
        success = False
        try:
            variables[variable_name] = eval(value)
            success = True
            logging.debug(f"Set variable '{variable_name}' to '{value}'")
        except Exception as e:
            logging.error(f"Error setting variable '{variable_name}' to '{value}': {e}", exc_info=True)
            success = False
        
        if success:
            # Handle on_success
            on_success = set_variable.get('on_success')
            if on_success is not None:
                if isinstance(on_success, str):
                    return self.str_to_bool(on_success)
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error
            on_error = set_variable.get('on_error')
            if on_error is not None:
                if isinstance(on_error, str):
                    return self.str_to_bool(on_error)
                elif isinstance(on_error, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
            
    def execute_operation(self, breadcrumbs, operation, variables=None):
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
            return self.execute_locate_image(breadcrumbs, operation.get('locate_image'), variables)
        elif 'keyboard_input' in operation:
            return self.execute_keyboard_input(breadcrumbs, operation.get('keyboard_input'), variables)
        elif 'play_audio' in operation:
            return self.execute_play_audio(breadcrumbs, operation.get('play_audio'), variables)
        elif 'set_variable' in operation:
            return self.execute_set_variable(breadcrumbs, operation.get('set_variable'), variables)
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
        logging.debug(f"Start executing instruction: '{instruction_name}'")

        if self.config is None:
            logging.error("Configuration not loaded. Call load_config first.")
            return False
            
        if variables is None:
            variables = {}
        
        if instruction_name not in self.config:
            logging.error(f"Instruction: '{instruction_name}' not found in configuration")
            return False
        
        instruction_list = self.config[instruction_name]
        breadcrumbs = instruction_name
        # If instruction_list is a list, process each item
        result = True
        if isinstance(instruction_list, list):
            for instruction_item in instruction_list:
                if result is False:
                    break
                for operation_name, operation in instruction_item.items():
                    result = self.execute_operation( breadcrumbs, {operation_name: operation}, variables)
                    
                    # If an operation returns False, stop processing
                    if result is False:
                        logging.warning(f"Operation: '{operation_name} 'returned False, stopping execution")
                        break
        
        # If it's a dictionary, just execute it
        elif isinstance(instruction_list, dict):
            result = self.execute_operation(breadcrumbs, instruction_list, variables)
        
        logging.debug(f"Finished executing instruction: '{instruction_name}' with result: {result}")
        return result