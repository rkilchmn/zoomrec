from errno import ELIBACC
import logging
import os
import psutil 
import random
import signal
import subprocess
import time
import atexit
import shlex
import threading
import pyautogui
from pathlib import Path
from datetime import datetime

from shared.events import Events, EventType, EventField, EventStatus, EventInstructionAttribute, EventInstructionProcess, EventInstructionPostprocess  
from shared.users import UserField
from shared.users_api import UserAPI
from shared.events_api import EventAPI
from shared.utilities import start_debug, end_process, convert_to_safe_filename, create_unique_filename, start_logging
import shared.constants as constants
from client.automation import Automation

start_logging(constants.LOG_CLIENT_FILENAME)
start_debug(constants.DEBUG_MODULE_ZOOMREC_CLIENT, os.getenv('DEBUG_PORT_CLIENT'))

# Get vars
BASE_PATH = os.getenv('ZOOMREC_HOME')
IMG_PATH = os.path.join(BASE_PATH, constants.IMG_DIR)
REC_PATH = os.path.join(BASE_PATH, constants.RECORDINGS_DIR)
AUDIO_PATH = os.path.join(BASE_PATH, constants.AUDIO_DIR) 
LOG_PATH = os.path.join(BASE_PATH, constants.LOG_DIR)
DEBUG_PATH = os.path.join(LOG_PATH, constants.DEBUG_DIR)

FFMPEG_INPUT_PARAMS = os.getenv('FFMPEG_INPUT_PARAMS')
FFMPEG_OUTPUT_PARAMS = os.getenv('FFMPEG_OUTPUT_PARAMS')

CLIENT_ID = os.getenv('CLIENT_ID')

SSH_SERVER_URL = os.getenv('SSH_SERVER_URL')
SSH_IDENTITY_FILE = os.getenv('SSH_IDENTITY_FILE')

# process variables
zoom_proc = None
ffmpeg_recording_proc = None
ffmpeg_recording_join_proc = None
postprocess_proc = None

# Get the directory where this module is located
SCRIPT_DIR = Path(__file__).parent.absolute()

def cleanup():
    end_process(zoom_proc)
    end_process(ffmpeg_recording_proc)
    end_process(ffmpeg_recording_join_proc)
    end_process(postprocess_proc)

atexit.register(cleanup)

def getIntEnv( env_str, default_value):
    int_val = default_value
    try:
        val_str = os.getenv(env_str)
        if val_str:
            int_val = int(val_str)
    except ValueError or TypeError:
        logging.error(f"error converting env {env_str} value {val_str} to integer. Default value {default_value} used.")

    return int_val

LEAD_TIME_SEC = getIntEnv( 'LEAD_TIME_SEC', 60) # start meeting x secs before official start date
TRAIL_TIME_SEC = getIntEnv( 'TRAIL_TIME_SEC', 300) # end meeting x secs after official end date

# client mode (get meetings from server)
SERVER_USERNAME = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD')
SERVER_URL = os.getenv('SERVER_URL')

DISPLAY_NAME = os.getenv('DISPLAY_NAME')
if DISPLAY_NAME is None or  len(DISPLAY_NAME) < 3:
    NAME_LIST = [
        'iPhone',
        'iPad',
        'Macbook',
        'Desktop',
        'Huawei',
        'Mobile',
        'PC',
        'Windows',
        'Home',
        'MyPC',
        'Computer',
        'Android'
    ]
    DISPLAY_NAME = random.choice(NAME_LIST)

def find_process_id_by_name(process_name):
    list_of_process_objects = []
    # Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
            # Check if process name contains the given name string.
            if process_name.lower() in pinfo['name'].lower():
                list_of_process_objects.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return list_of_process_objects

def start_recording(filename):

    # Start recording
    width, height = pyautogui.size()
    resolution = str(width) + 'x' + str(height)
    disp = os.getenv('DISPLAY')

    logging.info(f"Start recording {filename}")

    command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
        resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
        " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

    logging.debug(f"Recording command: {command}")

    command = shlex.split(command)
    subprocess_info = subprocess.Popen(
        command, stdout=subprocess.PIPE, shell=False, preexec_fn=os.setsid)
    
    return subprocess_info

class PostprocessAndTransferThread:
    def __init__(self, recording_basename, event, event_api):
        self.recording_basename = recording_basename
        self.event = event
        self.event_api = event_api

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):

        # Define desired postprocess execution order
        def postprocess_order(step):
            EXECUTION_ORDER = [
                EventInstructionPostprocess.TRANSCRIBE.value,
                EventInstructionPostprocess.TRANSLATE.value,
                EventInstructionPostprocess.CUSTOM.value,
                EventInstructionPostprocess.UPLOAD.value
            ]

            if not isinstance(step, dict):
                return len(EXECUTION_ORDER)
            for idx, key in enumerate(EXECUTION_ORDER):
                if key in step:
                    return idx
            return len(EXECUTION_ORDER)

        try:
            event = self.event
            event_api = self.event_api
            recording_basename = self.recording_basename

            # start postprocessing
            postprocessing_start = Events.now(event)
            txt = f"Started postprocessing phase at {postprocessing_start.strftime(constants.DATETIME_FORMAT)}"
            logging.info(txt)
            print_console(txt)

            filename_postprocess = None
            if recording_basename:
                # Consolidate videos if multiple recordings of same meeting
                command = f"{SCRIPT_DIR}/concatenate_video.sh '{os.path.join(REC_PATH, recording_basename)}' {constants.VIDEO_EXTENSION} yes"
                logging.debug(f"Consolidate video command: {command}")
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error(f"Error consolidating video: {result.stderr}")
                else:
                    logging.debug(f"Consolidated video: {result.stdout}")
                    filename_postprocess = os.path.join(REC_PATH, f"{recording_basename}.{constants.VIDEO_EXTENSION}")

                # postprocessing instruction
                postprocess = Events.get_instruction_attribute(EventInstructionAttribute.POSTPROCESS, event)
                postprocess_sorted = sorted(postprocess, key=postprocess_order)
                for step in postprocess_sorted:
                    command = None
                    for key, value in step.items():
                        match key:
                            case EventInstructionPostprocess.TRANSCRIBE.value:
                                command = f"{SCRIPT_DIR}/transcribe_video.sh {key} {filename_postprocess}"
                            case EventInstructionPostprocess.TRANSLATE.value:
                                command = f"{SCRIPT_DIR}/transcribe_video.sh {key}={value['language'] if 'language' in value else 'en'} {filename_postprocess}"
                            case EventInstructionPostprocess.UPLOAD.value:
                                if SSH_SERVER_URL:
                                    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                                        user = user_api.get(filters=[[UserField.KEY.value, "=", event[EventField.USER_KEY.value]]])[0]
                                    command = (
                                        f"{SCRIPT_DIR}/sftp_upload.sh '{os.path.join(REC_PATH, recording_basename)}' "
                                        f"'{constants.SFTP_ADMIN_USERNAME}@{SSH_SERVER_URL}' "
                                        f"'{os.path.join(BASE_PATH, constants.SSH_IDENTITY_FILE)}' "
                                        f"'{user[UserField.LOGIN.value]}/{constants.RECORDINGS_DIR}' {value['delete'] if 'delete' in value else 'true'}"
                                    )
                                else:
                                    logging.error("SFTP transfer to server cannot be initiated: SSH_SERVER_URL not specified.")
                            case EventInstructionPostprocess.CUSTOM.value:
                                # Handle both single task (dict) and multiple tasks (list)
                                tasks = value if isinstance(value, list) else [value]
                                commands = []
                                
                                for task in tasks:
                                    if not isinstance(task, dict) or 'task' not in task:
                                        logging.error(f"Invalid custom task format: {task}")
                                        continue
                                    
                                    # Build command for this task
                                    script_name = task['task']
                                    script_path = os.path.join(SCRIPT_DIR, f"{script_name}")
                                    
                                    # Check if script exists and is executable
                                    if not os.path.isfile(script_path) or not os.access(script_path, os.X_OK):
                                        logging.error(f"Script not found or not executable: {script_path}")
                                        continue
                                    
                                    # Build the command with the script and its arguments
                                    cmd = f"{script_path} {filename_postprocess}"
                                    for param, param_value in task.items():
                                        if param != 'task':  # Skip task as it's used as script name
                                            cmd += f" --{param} '{param_value}'"  # Quote the parameter value
                                    commands.append(cmd)
                                
                                # Join commands with && to run them sequentially
                                command = " && ".join(commands) if commands else ""
                            case _:
                                logging.error(f"Unknown postprocessing step: {key}")
                                continue
                            
                    # run command
                    if command:
                        postprocessing_step_start = Events.now(event)
                        txt = f"Started postprocessing step '{key}' with args {value} at {postprocessing_step_start.strftime(constants.DATETIME_FORMAT)}"
                        logging.info(txt)
                        print_console(txt)

                        logging.debug(f"Postprocessing task '{key}' command: {command}")
                        postprocess_proc = subprocess.Popen(
                            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
                        if postprocess_proc:
                            stdout, stderr = postprocess_proc.communicate()
                            if postprocess_proc.returncode == 0:
                                postprocessing_step_end = Events.now(event)
                                postprocessing_step_duration = postprocessing_step_end - postprocessing_step_start
                                logging.info(f"Postprocessing task '{key}' completed successfully at {postprocessing_step_end.strftime(constants.DATETIME_FORMAT)} after {str(postprocessing_step_duration).split('.')[0]}")
                            else:
                                logging.error(f"Postprocessing task '{key}' failed with return code: {postprocess_proc.returncode} and error: {stderr.decode().strip()}")
                            # debug output
                            logging.debug(f"Postprocessing task '{key}' stdout: {stdout.decode().strip()}")
                            logging.debug(f"Postprocessing task '{key}' stderr: {stderr.decode().strip()}")
                            postprocess_proc = None
                        else:
                            logging.error(f"Postprocessing task '{key}' failed to start.")
                            
            # update event status
            try:
                event[EventField.STATUS.value] = EventStatus.ENDED.value
                event[EventField.ASSIGNED.value] = ''
                event[EventField.ASSIGNED_TIMESTAMP.value] = ''
                event_api.update(event)
            except Exception as e:
                logging.error(f"Error updating event: {e}")
        except Exception as e:
            logging.error(f"Error in postprocess_and_transfer thread: {e}")
    
def join(event_key, dtstart_instance, dtend_instance, dtstart_instance_lead, dtend_instance_trail):
    try:
        with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
            event = event_api.get(filters=[[EventField.KEY.value, "=", event_key]])[0]
            if int(event[EventField.STATUS.value]) == int(EventStatus.SCHEDULED.value):
                if not event[EventField.ASSIGNED.value]:
                    event[EventField.ASSIGNED.value] = CLIENT_ID
                elif event[EventField.ASSIGNED.value] != CLIENT_ID:
                    logging.warning(f"{Events.nameStr(event)} already assigned to another client: '{event[EventField.ASSIGNED.value]}'")
                    return
                else:
                    logging.info(f"{Events.nameStr(event)} already assigned to client: '{event[EventField.ASSIGNED.value]}'")

                event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
                try:
                    event_api.update(event)
                except Exception as e:
                    logging.error(f"Error updating event: {e}")
                    return

            meet_id = event[EventField.ID.value]
            meet_pw = event[EventField.PASSWORD.value]
            meet_url = event[EventField.URL.value]
            duration = int(event[EventField.DURATION.value]) * 60
            description = event[EventField.TITLE.value]

            info_str = f"Joining meeting event with title: '{description}'"
            logging.info(info_str)
            print_console(info_str)

            if logging.getLogger().level == logging.DEBUG:
                ffmpeg_recording_join_proc = start_recording( 
                    os.path.join(REC_PATH, 
                        create_unique_filename(REC_PATH, 
                            convert_to_safe_filename(f"{description}-JOIN-{dtstart_instance.strftime( constants.DATETIME_FORMAT)}"), 
                            constants.VIDEO_EXTENSION
                        )
                    )
                )

            # Exit Zoom if running
            exit_process_by_name("zoom")

            join_by_url = meet_url.startswith('https://') or meet_url.startswith('http://')

            # Start Zoom
            if join_by_url:
                logging.info("Starting zoom with url")
                zoom_proc = subprocess.Popen(f'zoom --url="{meet_url}"', stdout=subprocess.PIPE,
                                        shell=True, preexec_fn=os.setsid)
            else:
                zoom_proc = subprocess.Popen("zoom", stdout=subprocess.PIPE,
                                        shell=True, preexec_fn=os.setsid)

            # Wait while zoom process is there
            list_of_process_ids = find_process_id_by_name('zoom')   
            while len(list_of_process_ids) <= 0:
                logging.info("No Running Zoom Process found!")
                list_of_process_ids = find_process_id_by_name('zoom')
                time.sleep(1)

            logging.info("Zoom started!")
            
            variables = {
                "MEET_ID": meet_id,
                "DISPLAY_NAME": DISPLAY_NAME,
                "PASSWORD": meet_pw,
                "HOST_ENDED_MEETING": False
            }
            
            # Create global instance of Automation with proper configuration and load the YAML config
            # Initialize Automation with base path
            auto_yaml = Automation(BASE_PATH)
            # Join meeting executing automation by config
            joined = auto_yaml.execute_instruction('join', variables)
            
            end_process(ffmpeg_recording_join_proc)
            
            if not joined:
                logging.error("Failed to join meeting!")
                end_process(zoom_proc)
                return False
            
            meeting_joined = Events.now(event)
            logging.info(f"Joined meeting at {meeting_joined.strftime(constants.DATETIME_FORMAT)}")

            process = Events.get_instruction_attribute(EventInstructionAttribute.PROCESS, event)       
            should_record = any(isinstance(step, dict) and EventInstructionProcess.RECORD.value in step for step in process) if isinstance(process, list) else False
            recording_basename = None
            if should_record:
                recording_basename = f"{description}-{dtstart_instance.strftime(constants.DATETIME_FORMAT)}"
                recording_basename = convert_to_safe_filename(recording_basename)
                filename_recording = os.path.join(REC_PATH, create_unique_filename(REC_PATH, recording_basename, constants.VIDEO_EXTENSION))

                ffmpeg_recording_proc = start_recording(filename_recording)

            # update event
            try:
                event[EventField.STATUS.value] = EventStatus.PROCESS.value
                event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
                event_api.update(event)
            except Exception as e:
                logging.error(f"Error updating event: {e}")

            now_in_tz = None
            meeting_ongoing = True
            meeting_duration_exceeded = None
            while meeting_ongoing:
                meeting_ongoing = auto_yaml.execute_instruction('ongoing', variables)
                now_in_tz = Events.now(event)
                if (now_in_tz <= dtend_instance_trail):
                    time_remaining = dtend_instance_trail - now_in_tz
                    # console not visible
                    # print_console(f"Meeting ends in {time_remaining}")
                else:
                    meeting_duration_exceeded = True
                    meeting_ongoing = False
                
                if meeting_ongoing:
                    time.sleep(constants.INTERVAL_CHECK_MEETING_ONGOING)

            meeting_elapsed = now_in_tz - meeting_joined

            # end zoom and ffmeg recording
            end_process(zoom_proc)
            end_process(ffmpeg_recording_proc)

            if not (meeting_duration_exceeded or variables['HOST_ENDED_MEETING']):
                logging.error(f"Meeting prematurely ended at {now_in_tz.strftime(constants.DATETIME_FORMAT)} after {str(meeting_elapsed).split(".")[0]}")
                return False

            logging.info(f"Meeting ended at {now_in_tz.strftime(constants.DATETIME_FORMAT)} after {str(meeting_elapsed).split(".")[0]}")

            event[EventField.STATUS.value] = EventStatus.POSTPROCESS.value
            event[EventField.ASSIGNED.value] = CLIENT_ID
            event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
            try:
                event_api.update(event)
            except Exception as e:
                logging.error(f"Error updating event: {e}")
            
            # Start postprocessing and transfer in a separate thread
            PostprocessAndTransferThread(recording_basename, event, event_api)

            # now other events can be joined while postprocessing is still ongoing
            return True
    except Exception as e:
        logging.error(f"Error joining event: {e}", exc_info=True)
        return False

def exit_process_by_name(name):
    list_of_process_ids = find_process_id_by_name(name)
    if len(list_of_process_ids) > 0:
        logging.info(name + " process exists | killing..")
        for elem in list_of_process_ids:
            process_id = elem['pid']
            try:
                os.kill(process_id, signal.SIGKILL)
            except Exception as ex:
                logging.error("Could not terminate " + name +
                              "[" + str(process_id) + "]: " + str(ex))

def get_zoom_version():
    try:
        # Execute the command to get the installed version of the Zoom package, suppressing warnings
        result = subprocess.run(['apt', 'list', 'zoom', '--installed'], capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        
        # Look for the line that starts with "zoom/"
        for line in output.split('\n'):
            if line.startswith("zoom/"):
                version = line.split()[1]  # Get the version part
                return version
        
        return None
    except subprocess.CalledProcessError:
        return None

def print_console(message, no_scroll=True):
    """Print a message to the console with carriage return and flush.
    Message is padded to 89 characters to clear any previous longer messages.
    If no_scroll is True, then the same (last line is overwritten)"""
    padded_message = f"{message:<{constants.TERMINAL_WIDTH}}"  # Left align and pad with spaces to x chars
    if no_scroll:
        print(padded_message, end="\r", flush=True)
    else:
        print(padded_message, flush=True)

def main():
    # loop to retrive next event and wait for it to join
    with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
        while True:
            try:      
                next_event = event_api.get_next(CLIENT_ID, EventType.ZOOM.value, LEAD_TIME_SEC, TRAIL_TIME_SEC)
                if next_event:  
                    #  convert from iso and apply timezone
                    next_event['dtstart_instance'] = Events.replaceTimezone(datetime.fromisoformat(next_event['dtstart_instance']), next_event['timezone'])
                    next_event['dtend_instance'] = Events.replaceTimezone(datetime.fromisoformat(next_event['dtend_instance']), next_event['timezone'])
                    next_event['dtstart_instance_lead'] = Events.replaceTimezone(datetime.fromisoformat(next_event['dtstart_instance_lead']), next_event['timezone'])
                    next_event['dtend_instance_trail'] = Events.replaceTimezone(datetime.fromisoformat(next_event['dtend_instance_trail']), next_event['timezone'])
                    next_event['dtnow'] = Events.replaceTimezone(datetime.fromisoformat(next_event['dtnow']), next_event['timezone'])
                            
                if next_event and next_event['dtstart_instance_lead'] <= next_event['dtnow'] and next_event['dtnow'] <= next_event['dtend_instance_trail']:
                    join( next_event[EventField.KEY.value], next_event['dtstart_instance'], next_event['dtend_instance'], next_event['dtstart_instance_lead'], next_event['dtend_instance_trail'])  
                else:                  
                    for _ in range(constants.INTERVAL_CHECK_NEXT_EVENT):
                        if next_event:
                            next_event['dtnow'] = Events.now( next_event)
                            time_diff = next_event["dtstart_instance_lead"] - next_event["dtnow"]
                            if time_diff.total_seconds() > 0: # for short time when updating this becomes negative
                                formatted_time = str(time_diff).split(".")[0]  # Removes microseconds
                                print_console(f"Next event with title: '{next_event[EventField.TITLE.value]}' starts in {formatted_time}")
                        else:
                            print_console("No upcoming events")
                        
                        time.sleep(1)
                
            except Exception as e:
                logging.error(f"Monitoring event error: {str(e)}")
                print_console(f"Monitoring event error: {e}")

if __name__ == '__main__':
    version = get_zoom_version()
    print_console(f"Zoom version: {version}", False)
    main()
