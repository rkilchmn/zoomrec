import yaml
import re
import logging
import os
import time
import pyautogui  
import subprocess
import random
from types import SimpleNamespace
from simpleeval import SimpleEval

import shared.constants as constants
from shared.utilities import convert_to_safe_filename


class ExprNode:
    def __init__(self, expr: str):
        self.expr = expr

    def eval(self, context: dict):
        e = SimpleEval()
        for key, value in context.items():
            e.names[key] = value
        return e.eval(self.expr)

    def __repr__(self):
        return f"ExprNode({self.expr!r})"

def expr_constructor(loader, node):
    value = loader.construct_scalar(node)
    return ExprNode(value)

yaml.SafeLoader.add_constructor("!expr", expr_constructor)

# Disable failsafe
pyautogui.FAILSAFE = False

class Automation:
    """
    Class for handling YAML configuration operations automation.
    """
    
    def __init__(self, default_path, config_path=None, audio_path=None, screenshot_path=None, event_basename=None):
        """
        Initialize the Automation class
        
        Args:
            default_path: Path containing default automation.yaml and IMG directory
            config_path: Optional path containing custom automation.yaml and IMG directory
            audio_path: Path containing audio files
            screenshot_path: Path for storing debug information
        """
        self.config = None
        self.default_path = os.path.abspath(default_path)
        self.config_path = os.path.abspath(config_path) if config_path else None
        self.audio_path = os.path.abspath(audio_path) if audio_path else None
        self.screenshot_path = screenshot_path
        self.event_basename = event_basename
        
        # Import constants
        from shared import constants
        
        # Set up paths
        self.default_img_path = os.path.join(self.default_path, constants.IMG_DIR)
        self.config_img_path = os.path.join(self.config_path, constants.IMG_DIR) if self.config_path else None
       
        # Load configuration with fallback
        self._load_config_with_fallback()
    
    def _load_config_with_fallback(self):
        """Load configuration with fallback from config_path to default_path"""
        # Try to load from config_path first
        if self.config_path and os.path.isfile(os.path.join(self.config_path, constants.CLIENT_AUTOMATION_CONFIG_FILENAME)):
            config_file = os.path.join(self.config_path, constants.CLIENT_AUTOMATION_CONFIG_FILENAME)
            self.load_config(config_file)
        # Fall back to default_path
        elif os.path.isfile(os.path.join(self.default_path, constants.CLIENT_AUTOMATION_CONFIG_FILENAME)):
            config_file = os.path.join(self.default_path, constants.CLIENT_AUTOMATION_CONFIG_FILENAME)
            self.load_config(config_file)
        else:
            raise FileNotFoundError(f"Automation YAML configuration file '{constants.CLIENT_AUTOMATION_CONFIG_FILENAME}' not found in ' {self.config_path}' or '{self.default_path}'")

    
    def get_image_path(self, filename):
        """
        Get the full path to an image file, checking config path first, then default path
        
        Args:
            filename: Name of the image file
            
        Returns:
            Full path to the image file, or None if not found
        """
        # Check in config image path first
        if self.config_img_path and os.path.isfile(os.path.join(self.config_img_path, filename)):
            return os.path.join(self.config_img_path, filename)
        # Fall back to default image path
        if os.path.isfile(os.path.join(self.default_img_path, filename)):
            return os.path.join(self.default_img_path, filename)
        return None
    
    def load_config(self, file_path):
        """
        Load and store the YAML configuration
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            The parsed YAML content as a dictionary
        """
        self.config = self.read_config(file_path)
        if self.config is None:
            logging.error(f"Error reading Automation YAML configuration file: {file_path}")
            return None
        else:
            logging.info(f"Loaded Automation YAML configuration file: {file_path}")
            return self.config

    @staticmethod
    def validate_bool(value):
        """Validate that value is a boolean."""
        if not isinstance(value, bool):
            raise ValueError(f"Invalid boolean value: {value}")
        return value
    
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
            logging.error(f"Error reading Automation YAML configuration file: {file_path}: {e}")
            return None
    
    @staticmethod
    def resolve_value(attribute, context):
       
        # Handle ExprNode instances
        if isinstance(attribute, ExprNode):
            return attribute.eval(context)

        return attribute
    
    @staticmethod
    def resolve_config_value(config, key, context, default=None):
        """
        Resolve a configuration value, automatically evaluating ExprNode instances.
        
        Args:
            config: Dictionary containing the configuration
            key: Key to look up
            context: Evaluation context for ExprNode expressions
            default: Default value if key not found
            
        Returns:
            The resolved value, with ExprNode instances evaluated
        """
        value = config.get(key, default)
        return Automation.resolve_value(value, context)
    
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
        
        # Prepare context with 'VARIABLES' key
        context = {'VARIABLES': variables}

        def compute_region(region):
            if not isinstance(region, dict):
                return None
            
            def to_float(value, name):
                try:
                    return float(value) if value is not None else None
                except (TypeError, ValueError) as e:
                    logging.error(f"Error converting {name} to float: {e}")
                    return None
            
            tlx = to_float(self.resolve_config_value(region, 'top_left_x', context), 'top_left_x')
            tly = to_float(self.resolve_config_value(region, 'top_left_y', context), 'top_left_y')
            brx = to_float(self.resolve_config_value(region, 'bottom_right_x', context), 'bottom_right_x')
            bry = to_float(self.resolve_config_value(region, 'bottom_right_y', context), 'bottom_right_y')
            
            if None in (tlx, tly, brx, bry):
                return None
            else:
                return (int(tlx), int(tly), int(brx), int(bry))
                
        image = self.resolve_config_value(locate_image, 'image', context)
        click = self.validate_bool(self.resolve_config_value(locate_image, 'click', context, False))
        iterate = self.resolve_config_value(locate_image, 'iterate', context, 1)
        until_found = self.validate_bool(self.resolve_config_value(locate_image, 'until_found', context, True))
        sleep_time = self.resolve_config_value(locate_image, 'sleep', context, 0)
        confidence = self.resolve_config_value(locate_image, 'confidence', context, 0.9)
        minSearchTime = self.resolve_config_value(locate_image, 'minSearchTime', context, 0)
        region_def = self.resolve_config_value(locate_image, 'region', context)
        set_variable = self.resolve_config_value(locate_image, 'set_variable', context)
        debug_screenshot = self.validate_bool(self.resolve_config_value(locate_image, 'debug_screenshot', context, True))

        breadcrumbs += f"/LocateImage:[{os.path.splitext(image)[0]}]"
        logging.debug(f"{breadcrumbs}")

        success = False
        image_path = self.get_image_path(image)
        if image_path is None:
            logging.error(f"Image '{image}' not found")
            return False
        else:
            region_box = None
            if region_def is not None:
                region_box = compute_region(region_def)

            for i in range(iterate):
                result = self.wrap(pyautogui.locateOnScreen, image_path, confidence=confidence, minSearchTime=minSearchTime, region=region_box)

                if result is not None:
                    left, top, width, height = result.left, result.top, result.width, result.height
                    x = left + width // 2
                    y = top + height // 2

                    if set_variable:
                        # Store result in structured format under the given name
                        variables[set_variable] = SimpleNamespace(
                            center_x=x,
                            center_y=y,
                            width=width,
                            height=height,
                            # Add some utility properties
                            left=left,
                            top=top,
                            right=left + width,
                            bottom=top + height
                        )

                    if click:
                        pyautogui.click(x, y)
                        logging.debug(f"Clicked at position {x}, {y}")

                if until_found:
                    if result is not None:
                        success = True
                        break
                else:
                    if result is None:
                        success = True
                        break

                if i < iterate - 1 and sleep_time > 0:
                    time.sleep(sleep_time)

        logging.debug(f"Image: {image} result after {i+1} of {iterate} iterations: {('FOUND' if success else 'NOT FOUND')} success: {success} ")

        if success:
            # Handle on_success
            on_success = locate_image.get('on_success')
            if on_success is not None:
                if isinstance(on_success, bool):
                    return on_success
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Debug screenshot
            if logging.getLogger().level == logging.DEBUG and \
                self.screenshot_path is not None and \
                self.event_basename is not None and \
                debug_screenshot:
                pyautogui.screenshot( 
                    os.path.join(self.screenshot_path, 
                        convert_to_safe_filename(time.strftime(constants.DATETIME_FORMAT_LOG) + "_" + breadcrumbs + ".png")))
                    
            # Handle on_error or on_error
            on_error = locate_image.get('on_error')
            if on_error is not None:
                if isinstance(on_error, bool):
                    return on_error
                elif isinstance(on_error, dict):
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
    
    def execute_keyboard_input(self, breadcrumbs, keyboard_input, variables=None):

        if variables is None:
            variables = {}
        
        # Prepare context with 'VARIABLES' key
        context = {'VARIABLES': variables}
            
        sequence = keyboard_input.get('sequence', [])

        breadcrumbs += f"/KeyboardInput[{len(sequence)}]"
        logging.debug(f"{breadcrumbs}")
        
        success = False
        try:
            for action in sequence:
                if 'press' in action:
                    key = self.resolve_value(action['press'], context)
                    pyautogui.press(key)
                    logging.debug(f"Pressed key: '{key}'")
            
                elif 'write' in action:
                    text = self.resolve_value(action['write'], context)
                    interval = self.resolve_config_value(action, 'interval', context, 0.1)  # Default interval
                    pyautogui.write(text, interval=interval)
                    logging.debug(f"Wrote text: '{text}'")
                
                elif 'hotkey' in action:
                    # Handle hotkey which can be in various formats
                    hotkey_data = action['hotkey']
                    
                    # Convert the hotkey data to a list of keys
                    if isinstance(hotkey_data, list):
                        keys = [self.resolve_value(k, context) for k in hotkey_data]
                    else:
                        # It's a string that needs parsing
                        hotkey_str = self.resolve_value(hotkey_data, context)
                        
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
                if isinstance(on_success, bool):
                    return on_success
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error or on_error
            on_error = keyboard_input.get('on_error')
            if on_error is not None:
                if isinstance(on_error, bool):
                    return on_error
                elif isinstance(on_error, dict):
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
    
    def execute_play_audio(self, breadcrumbs, play_audio, variables=None):
        if variables is None:
            variables = {}
        
        # Prepare context with 'VARIABLES' key
        context = {'VARIABLES': variables}
        
        try:
            # Check if specific audio file is specified
            specific_audio = self.resolve_config_value(play_audio, 'audio', context)

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
                if isinstance(on_success, bool):
                    return on_success
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error
            on_error = play_audio.get('on_error')
            if on_error is not None:
                if isinstance(on_error, bool):
                    return on_error
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
        
        # Prepare context with 'VARIABLES' key
        context = {'VARIABLES': variables}
        
        name = self.resolve_config_value(set_variable, 'name', context)
        value = self.resolve_config_value(set_variable, 'value', context)
        
        breadcrumbs += f"/SetVariable:[{name}={value}]"
        logging.debug(f"{breadcrumbs}")
        
        success = False
        try:
            variables[name] = value
            success = True
            logging.debug(f"Set variable '{name}' to '{value}'")
        except Exception as e:
            logging.error(f"Error setting variable '{name}' to '{value}': {e}", exc_info=True)
            success = False
        
        if success:
            # Handle on_success
            on_success = set_variable.get('on_success')
            if on_success is not None:
                if isinstance(on_success, bool):
                    return on_success
                elif isinstance(on_success, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_success, variables)
            return True
        else:
            # Handle on_error
            on_error = set_variable.get('on_error')
            if on_error is not None:
                if isinstance(on_error, bool):
                    return on_error
                elif isinstance(on_error, dict):
                    # If it's a dictionary, recursively process it
                    return self.execute_operation(breadcrumbs, on_error, variables)
            return False
            
    def execute_check(self, breadcrumbs, check, variables=None):
        """
        Execute a check operation
        
        Args:
            breadcrumbs: String tracking execution path
            check: Dictionary containing check configuration with 'condition' key
            variables: Dictionary of variables to check against
            
        Returns:
            Result based on success or failure of the condition
        """
        if variables is None:
            variables = {}
        
        # Prepare context with 'VARIABLES' key
        context = {'VARIABLES': variables}
        
        # Evaluate condition using resolve_config_value to support !expr
        condition = self.resolve_config_value(check, 'condition', context)
        
        result = condition
        
        breadcrumbs += f"/Check[{condition}]"
        logging.debug(f"{breadcrumbs}")
        
        try:
            # Convert to boolean
            result = bool(result)
            logging.debug(f"Check condition: {condition} -> {result}")
            
            if result:
                # Handle on_success
                on_success = check.get('on_success')
                if on_success is not None:
                    if isinstance(on_success, bool):
                        return on_success
                    elif isinstance(on_success, dict):
                        return self.execute_operation(breadcrumbs, on_success, variables)
                return True
            else:
                # Handle on_error
                on_error = check.get('on_error')
                if on_error is not None:
                    if isinstance(on_error, bool):
                        return on_error
                    elif isinstance(on_error, dict):
                        return self.execute_operation(breadcrumbs, on_error, variables)
                return False
                
        except Exception as e:
            logging.error(f"Error evaluating condition '{condition}': {e}", exc_info=True)
            # Handle error case
            on_error = check.get('on_error')
            if on_error is not None:
                if isinstance(on_error, bool):
                    return on_error
                elif isinstance(on_error, dict):
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
        elif 'check' in operation:
            return self.execute_check(breadcrumbs, operation.get('check'), variables)
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
        breadcrumbs = self.event_basename + "/" + instruction_name
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
                        logging.warning(f"Instruction: '{instruction_name}' Operation: '{operation_name}' Details: '{operation}' returned False, stopping execution")
                        break
        
        # If it's a dictionary, just execute it
        elif isinstance(instruction_list, dict):
            result = self.execute_operation(breadcrumbs, instruction_list, variables)
        
        logging.debug(f"Finished executing instruction: '{instruction_name}' with result: {result}")
        return result