import logging
import os
import psutil 
import random
import signal
import subprocess
import threading
import time
import datetime
import atexit
from datetime import datetime, timedelta
from events import Events, EventType, EventField, EventStatus, EventInstructionAttribute
import debugpy
from events_api import get_next_event_api, update_event_api  # Ensure you import the function
from utilities import convert_to_safe_filename
from automation import Automation
import pyautogui  
import traceback

# Turn DEBUG on:
#   - screenshot on error
#   - record joining
#   - do not exit container on error
#   - wait for debugger attach
DEBUG = True if os.getenv('DEBUG') == 'zoomrec' else False

if DEBUG:
    debugpy.listen(("0.0.0.0", 5678))
    print("Waiting for debugger attach")
    debugpy.wait_for_client()
    print("Debugger attached")

# Get vars
BASE_PATH = os.getenv('ZOOMREC_HOME')
IMG_PATH = os.path.join(BASE_PATH, "img")
REC_PATH = os.path.join(BASE_PATH, "recordings")
AUDIO_PATH = os.path.join(BASE_PATH, "audio")
DEBUG_PATH = os.path.join(REC_PATH, "screenshots")

FFMPEG_INPUT_PARAMS = os.getenv('FFMPEG_INPUT_PARAMS')
FFMPEG_OUTPUT_PARAMS = os.getenv('FFMPEG_OUTPUT_PARAMS')

CLIENT_ID = os.getenv('CLIENT_ID')

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

TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"

# initialization of global vars
ONGOING_MEETING = False
VIDEO_PANEL_HIDED = False

# Config path for YAML configuration
config_path = os.path.join(BASE_PATH, "zoom.yaml")

# Get the current date and time
now = datetime.now()

# Format the date and time in the desired format
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

# Create the log file name with the timestamp
log_file = DEBUG_PATH + "/{}.log".format(timestamp)
logLevel = getattr(logging, os.getenv( "LOG_LEVEL", "INFO"), logging.INFO)

# Configure the logging
logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=logLevel)

class BackgroundThread:

    def __init__(self, auto_yaml, interval=10):
        # Sleep interval between
        self.interval = interval
        self.auto_yaml = auto_yaml

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        global ONGOING_MEETING
        ONGOING_MEETING = True

        logging.info("Check continuously if meeting has ended..")

        while ONGOING_MEETING:
            ONGOING_MEETING = self.auto_yaml.execute_instruction('ongoing', {})

            time.sleep(self.interval)

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

    logging.debug("Start recording joining process..")

    command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
        resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
        " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

    logging.debug(f"Recording command: {command}")

    subprocess_info = subprocess.Popen(
        command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
    
    atexit.register(os.killpg, os.getpgid(
        subprocess_info.pid), signal.SIGQUIT)
    
    return subprocess_info
    
def join(event, dtstart_instance, dtend_instance):
    global VIDEO_PANEL_HIDED
    
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
            update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
        except Exception as e:
            logging.error(f"Error updating event: {e}", exc_info=True)
            return

    meet_id = event[EventField.ID.value]
    meet_pw = event[EventField.PASSWORD.value]
    meet_url = event[EventField.URL.value]
    duration = int(event[EventField.DURATION.value]) * 60
    description = event[EventField.TITLE.value]

    str = f"Joining meeting event with title: '{description}'"
    logging.info(str)
    print(str, end="\r", flush=True)

    ffmpeg_debug = None
    if logging.getLogger().level == logging.DEBUG:
        ffmpeg_debug = start_recording( filename = os.path.join( 
            REC_PATH, convert_to_safe_filename( time.strftime(TIME_FORMAT) + "-" + description + "-JOIN.mkv")))

    # Exit Zoom if running
    exit_process_by_name("zoom")

    join_by_url = meet_url.startswith('https://') or meet_url.startswith('http://')

    # Start Zoom
    if join_by_url:
        logging.info("Starting zoom with url")
        zoom = subprocess.Popen(f'zoom --url="{meet_url}"', stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
    else:
        zoom = subprocess.Popen("zoom", stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)

    # Wait while zoom process is there
    list_of_process_ids = find_process_id_by_name('zoom')
    while len(list_of_process_ids) <= 0:
        logging.info("No Running Zoom Process found!")
        list_of_process_ids = find_process_id_by_name('zoom')
        time.sleep(1)

    logging.info("Zoom started!")
    start_date = datetime.now()
    
    variables = {
        "MEET_ID": meet_id,
        "DISPLAY_NAME": DISPLAY_NAME,
        "PASSWORD": meet_pw
    }
    
    # Create global instance of Automation with proper configuration and load the YAML config
    config_path = os.path.join(BASE_PATH, "zoom_auto.yaml")
    auto_yaml = Automation(img_path=IMG_PATH, debug_path=DEBUG_PATH, time_format=TIME_FORMAT, config_path=config_path)

    # Join meeting executing automation by config
    joined = auto_yaml.execute_instruction('join', variables)
    
    if not joined:
        logging.error("Failed to join meeting!")
        os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
        if logging.getLogger().level == logging.DEBUG and ffmpeg_debug is not None:
            # closing ffmpeg
            os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
            atexit.unregister(os.killpg)
        return

    # Start BackgroundThread
    BackgroundThread(auto_yaml)

    process = Events.get_instruction_attribute( EventInstructionAttribute.PROCESS, event)
    filename_recording = os.path.join(REC_PATH, convert_to_safe_filename(time.strftime( TIME_FORMAT) + "-" + description) + ".mkv")
    if process == 'record':
        ffmpeg = start_recording(filename_recording)

    # update event
    try:
        event[EventField.STATUS.value] = EventStatus.PROCESS.value
        event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
        update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
    except Exception as e:
        logging.error(f"Error updating event: {e}", exc_info=True)

    now_in_tz = None
    meeting_running = True
    while meeting_running:
        now_in_tz = Events.now(event)
        if (dtstart_instance <= now_in_tz <= dtend_instance) and ONGOING_MEETING:
            time_remaining = dtend_instance - now_in_tz
            print(f"Meeting ends in {time_remaining}", end="\r", flush=True)
        else:
            meeting_running = False
        time.sleep(5)

    logging.info("Meeting ends at %s" % now_in_tz)

    os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
    os.killpg(os.getpgid(ffmpeg.pid), signal.SIGQUIT)
    atexit.unregister(os.killpg)
                
    # postprocessing
    postprocess = Events.get_instruction_attribute( EventInstructionAttribute.POSTPROCESS, event)  
    if postprocess:
        command = f"./postprocess.sh {postprocess} '{filename_recording}'"
        logging.debug(f"Postprocess command: {command}")

        postprocess_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        
        atexit.register(os.killpg, os.getpgid(
            postprocess_process.pid), signal.SIGQUIT)
        
        if postprocess_process:
            posprocessing_start = datetime.now()
            txt = f"Started postprocessing task '{postprocess}'..."
            logging.info(txt)
            print(txt, end="\r", flush=True)
            event[EventField.STATUS.value] = EventStatus.POSTPROCESS.value
            event[EventField.ASSIGNED.value] = CLIENT_ID
            event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
            try:
                update_event_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
            except Exception as e:
                logging.error(f"Error updating event: {e}", exc_info=True)

            postprocess_process.wait()
            posprocessing_end = datetime.now()
            postprocessing_duration = posprocessing_end - posprocessing_start
            logging.info(f"Postprocessing task completed in {postprocessing_duration}")

        else:
            logging.error("Postprocessing script not found or not specified.")

    try:
        event[EventField.STATUS.value] = EventStatus.SCHEDULED.value
        event[EventField.ASSIGNED.value] = ''
        event[EventField.ASSIGNED_TIMESTAMP.value] = ''
        update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
    except Exception as e:
        logging.error(f"Error updating event: {e}", exc_info=True)

def play_audio(description):
    # Get all files in audio directory
    files=os.listdir(AUDIO_PATH)
    # Filter .wav files
    files=list(filter(lambda f: f.endswith(".wav"), files))
    # Check if .wav files available
    if len(files) > 0:
        unmute(description)
        # Get random file
        file=random.choice(files)
        path = os.path.join(AUDIO_PATH, file)
        # Use paplay to play .wav file on specific Output
        command = "/usr/bin/paplay --device=microphone -p " + path
        play = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        res, err = play.communicate()
        if play.returncode != 0:
            logging.error("Failed playing file! - " + str(play.returncode) + " - " + str(err))
        else:
            logging.debug("Successfully played audio file! - " + str(play.returncode))
        mute(description)
    else:
        logging.error("No .wav files found!")

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

def main():
    # loop to retrive next event and wait for it to join
    while True:
        try:
            next_event = get_next_event_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, CLIENT_ID, EventType.ZOOM.value, LEAD_TIME_SEC, TRAIL_TIME_SEC)
                        
            if next_event and next_event['dtstart_instance'] <= next_event['dtnow'] <= next_event['dtend_instance']:
                join(next_event, next_event['dtstart_instance'], next_event['dtend_instance'])                    
            
            for _ in range(60):
                if next_event:
                    next_event['dtnow'] = Events.now( next_event)
                    print(f"Next event with title: '{next_event[EventField.TITLE.value]}' starts in {next_event['dtstart_instance'] - next_event['dtnow']}", end="\r", flush=True)
                else:
                    print(f"No upcoming events", end="\r", flush=True)
                
                time.sleep(1)
            
        except Exception as e:
            logging.error(f"Monitoring event error: {str(e)}", exc_info=True)
            print(f"Monitoring event error: {str(e)}")

if __name__ == '__main__':
    version = get_zoom_version()
    print(f"Zoom version: {version}")
    main()
