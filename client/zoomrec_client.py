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
import pyautogui
from pathlib import Path
from datetime import datetime
import asyncio

from shared.events import Events, EventType, EventField, EventStatus, EventInstructionAttribute, EventInstructionProcess  
from shared.events_api import EventAPI
from shared.utilities import start_debug, end_process, convert_to_safe_filename, create_unique_filename, start_logging, format_template
import shared.constants as constants
from client.automation import Automation
from client.postprocessing import schedulePostprocess

start_logging(constants.LOG_CLIENT_FILENAME)
start_debug(constants.DEBUG_MODULE_ZOOMREC_CLIENT, os.getenv('DEBUG_PORT_CLIENT'))

# Get vars
BASE_PATH = os.getenv('ZOOMREC_HOME')
REC_PATH = os.path.join(BASE_PATH, constants.RECORDINGS_DIR)
LOG_PATH = os.path.join(BASE_PATH, constants.LOG_DIR)

FFMPEG_INPUT_PARAMS = os.getenv('FFMPEG_INPUT_PARAMS')
FFMPEG_OUTPUT_PARAMS = os.getenv('FFMPEG_OUTPUT_PARAMS')

CLIENT_ID = os.getenv('CLIENT_ID')

SSH_SERVER_URL = os.getenv('SSH_SERVER_URL')

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
    except (ValueError, TypeError):
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
    """
    Start screen recording using ffmpeg and verify the output file is writable.
    
    Args:
        filename (str): Path where the recording should be saved
        
    Returns:
        subprocess.Popen: Process handle for the recording, or None if failed to start
    """
    try:
        # # Create directory if it doesn't exist
        # os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # # Touch the file to check if we can write to the location
        # try:
        #     with open(filename, 'ab') as f:
        #         f.write(b'')  # Write empty bytes to create file if it doesn't exist
        # except IOError as e:
        #     logging.error(f"Cannot write to recording file {filename}: {e}")
        #     return None

        logging.debug(f"Starting recording to {filename}")
            
        width, height = pyautogui.size()
        resolution = f"{width}x{height}"
        disp = os.getenv('DISPLAY')

        command = (
            f"ffmpeg -nostats -loglevel error -f pulse -ac 2 -i speaker.monitor -f x11grab "
            f"-r 30 -s {resolution} {FFMPEG_INPUT_PARAMS} -i {disp} {FFMPEG_OUTPUT_PARAMS} "
            f"-threads 0 -async 1 -fps_mode cfr \"{filename}\""
        )

        logging.debug(f"Recording command: {command}")
        command = shlex.split(command)
        
        try:
            subprocess_info = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                preexec_fn=os.setsid
            )
            
            # Verify the process started and is writing to the file
            time.sleep(1)  # Give ffmpeg a moment to start
            
            if subprocess_info.poll() is not None:
                # Process already exited
                _, stderr = subprocess_info.communicate()
                logging.error(f"Failed to start ffmpeg: {stderr.decode('utf-8', 'replace')}")
                return None
                
            # # Check if file exists after a short delay
            # time.sleep(1)
            # if not os.path.exists(filename):
            #     logging.error(f"Recording file {filename} was not created")
            #     end_process(subprocess_info)
            #     return None
                
            logging.debug(f"Successfully started recording to {filename}")
            return subprocess_info
            
        except Exception as e:
            logging.error(f"Error starting recording: {e}")
            if 'subprocess_info' in locals():
                end_process(subprocess_info)
            return None
            
    except Exception as e:
        logging.error(f"Unexpected error in start_recording: {e}", exc_info=True)
        return None
    
async def join(event_key, dtstart_instance, dtend_instance, dtstart_instance_lead, dtend_instance_trail):
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
            # add dtstart_instance, dtend_instance, dtstart_instance_lead, dtend_instance_trail to event
            event['dtstart_instance'] = dtstart_instance
            event['dtend_instance'] = dtend_instance
            event['dtstart_instance_lead'] = dtstart_instance_lead
            event['dtend_instance_trail'] = dtend_instance_trail

            info_str = f"Joining meeting event with title: '{description}'"
            logging.info(info_str)
            print_console(info_str)

            if logging.getLogger().level == logging.DEBUG:
                basename_join_template = os.getenv('BASENAME_JOIN_TEMPLATE', constants.DEFAULT_BASENAME_JOIN_TEMPLATE)
                join_recording_basename = format_template(
                    template=basename_join_template,
                    data=event
                )
                join_recording_basename = convert_to_safe_filename(join_recording_basename)
                filename_join_recording = os.path.join(
                    REC_PATH,
                    create_unique_filename(REC_PATH, join_recording_basename, constants.VIDEO_EXTENSION)
                )
                ffmpeg_recording_join_proc = start_recording(filename_join_recording)

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
            
            # Get event type and corresponding subdirectory
            event_type_subdir = EventType.get_description(event[EventField.TYPE.value])
            
            # Set up paths based on event type
            default_path = os.path.join(BASE_PATH,constants.AUTOMATION_DIR, event_type_subdir)
            config_path = os.path.join(BASE_PATH, constants.CONFIG_DIR, constants.AUTOMATION_DIR, event_type_subdir)
            audio_path = os.path.join(BASE_PATH, constants.AUDIO_DIR)
            screenshot_path = os.path.join(BASE_PATH, constants.SCREENSHOT_DIR)
            
            # Create instance of Automation with the configured paths
            auto_yaml = Automation(
                default_path=default_path,
                config_path=config_path if os.path.exists(config_path) else None,
                audio_path=audio_path if os.path.exists(audio_path) else None,
                screenshot_path=screenshot_path
            )
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
                basename_template = os.getenv('BASENAME_TEMPLATE', constants.DEFAULT_BASENAME_TEMPLATE)
                # Generate basename using the template
                recording_basename = format_template(
                    template=basename_template,
                    data=event
                )
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

            # update event to ENDED to prevent re-joining 
            try:
                event[EventField.STATUS.value] = EventStatus.ENDED.value
                event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
                event_api.update(event)
            except Exception as e:
                logging.error(f"Error updating event: {e}")

            logging.info(f"Meeting ended at {now_in_tz.strftime(constants.DATETIME_FORMAT)} after {str(meeting_elapsed).split(".")[0]}")

            # start postprocessing using temporal.io
            handle = await schedulePostprocess(recording_basename, event, CLIENT_ID)
            logging.info(f"Started postprocessing with workflow id: '{handle.id}'")

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

async def main():
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
                    await join( next_event[EventField.KEY.value], next_event['dtstart_instance'], next_event['dtend_instance'], next_event['dtstart_instance_lead'], next_event['dtend_instance_trail'])  
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
    asyncio.run(main())
