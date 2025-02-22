import logging
import os
import psutil 
import pyautogui  # later zoom versions do not start anymore when pyautogui is imported, Zoom  5.13.0 (599) still works
from pyautogui import ImageNotFoundException
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
from events_api import delete_event_api, update_event_api, get_event_api  # Ensure you import the function

UC_CONNECTED_NOPOPUPS = 1

# Turn DEBUG on:
#   - screenshot on error
#   - record joining
#   - do not exit container on error
#   - wait for debugger attach
DEBUG = True if os.getenv('DEBUG') == 'True' else False

if DEBUG:
    debugpy.listen(("0.0.0.0", 5678))
    print("Waiting for debugger attach")
    debugpy.wait_for_client()
    print("Debugger attached")

# Disable failsafe
pyautogui.FAILSAFE = False

# Get vars
BASE_PATH = os.getenv('HOME')
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

# Get the current date and time
now = datetime.now()

# Format the date and time in the desired format
timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')

# Create the log file name with the timestamp
log_file = DEBUG_PATH + "/{}.log".format(timestamp)
logLevel = getattr(logging, os.getenv( "LOG_LEVEL", "INFO"), logging.INFO)

# Configure the logging
logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s %(message)s', level=logLevel)

def wrap(func, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        return result
    except ImageNotFoundException as e:
        # print(f"Image not found: {e}")
        return None
    except Exception as e:
        print(f"An unexpected exception occurred: {e}")
        # Handle the exception or log it as needed
        return None  # You can customize this return value based on your requirements



class BackgroundThread:

    def __init__(self, interval=10):
        # Sleep interval between
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        global ONGOING_MEETING
        ONGOING_MEETING = True

        logging.info("Check continuously if meeting has ended..")

        while ONGOING_MEETING:

            # Check if recording
            if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'meeting_is_being_recorded.png'), confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("This meeting is being recorded..")
                try:
                    x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                        IMG_PATH, 'got_it.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    logging.info("Accepted recording..")
                except TypeError:
                    logging.error("Could not accept recording!")

            # Check if ended
            if (wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'meeting_ended_by_host_1.png'),
                                         confidence=0.9) is not None or wrap( pyautogui.locateOnScreen, 
                os.path.join(IMG_PATH, 'meeting_ended_by_host_2.png'), confidence=0.9) is not None):
                ONGOING_MEETING = False
                logging.info("Meeting ended by host..")

            # Check if crash report window shows
            if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'zoom_crash_report_not_send.png'), confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("Zoom unexpectedly crashed..")
                try:
                    x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                        IMG_PATH, 'zoom_crash_report_not_send.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    logging.info("Close crash report window by not sending..")
                except TypeError:
                    logging.error("Could not close crash report window!")

            # Check "an unknown error occured" option "close" or "join from browser"
            if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'unknown_error_occurred.png'), confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("Zoom unknown error occured..")
                try:
                    x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                        IMG_PATH, 'unknown_error_close.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    logging.info("Close window unknown error occured..")
                except TypeError:
                    logging.error("Could not close unknown error occured window!")

            time.sleep(self.interval)

class HideViewOptionsThread:

    def __init__(self, description, interval=10):
        # Sleep interval between
        self.description = description
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def run(self):
        global VIDEO_PANEL_HIDED
    
        logging.info("Checking continuously if screensharing, polls or chats need hiding..")
        while ONGOING_MEETING:
            # Check if host is sharing poll results
            if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'host_is_sharing_poll_results.png'),
                                               confidence=0.9,
                                               minSearchTime=2) is not None):
                logging.info("Host is sharing poll results..")
                try:
                    x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                        IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9)
                    pyautogui.click(x, y)
                    try:
                        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                            IMG_PATH, 'exit.png'), confidence=0.9)
                        pyautogui.click(x, y)
                        logging.info("Closed poll results window..")
                    except TypeError:
                        logging.error("Could not exit poll results window!")
                        if logging.getLogger().level == logging.DEBUG:
                            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                                TIME_FORMAT) + "-" + self.description) + "_close_poll_results_error.png")
                except TypeError:
                    logging.error("Could not find poll results window anymore!")
                    if logging.getLogger().level == logging.DEBUG:
                        pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                            TIME_FORMAT) + "-" + self.description) + "_find_poll_results_error.png")

            # Check if view options available
            if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'view_options.png'), confidence=0.9) is not None:
                if not VIDEO_PANEL_HIDED:
                    logging.info("Screensharing active..")
                    try:
                        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                            IMG_PATH, 'view_options.png'), confidence=0.9)
                        pyautogui.click(x, y)
                        time.sleep(1)
                        # Hide video panel
                        if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'show_video_panel.png'),
                                                    confidence=0.9) is not None:
                            # Leave 'Show video panel' and move mouse from screen
                            pyautogui.moveTo(0, 100)
                            pyautogui.click(0, 100)
                            VIDEO_PANEL_HIDED = True
                            logging.info("Video panel hidden successfully..")
                        else:
                            try:
                                x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                                    IMG_PATH, 'hide_video_panel.png'), confidence=0.9) 
                                pyautogui.click(x, y)
                                # Move mouse from screen
                                pyautogui.moveTo(0, 100)
                                VIDEO_PANEL_HIDED = True
                                logging.info("Video panel hidden successfully..")
                            except TypeError:
                                logging.error("Could not hide video panel!")
                    except TypeError:
                        logging.error("Could not find view options!")

            # Check if meeting chat is on screen
            if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'meeting_chat.png'), confidence=0.9) is not None:
                logging.info("Meeting chat popup window detected..")
                # try to close window
                x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                            IMG_PATH, 'exit.png'), confidence=0.9)
                pyautogui.click(x, y)
                time.sleep(1)
                if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'meeting_chat.png'), confidence=0.9):
                    logging.info("Failed to close meeting chat popup window..")
        
                else:
                    logging.info("Successfully close meeting chat popup window..")

             # Check if "participant has enabled closed caption" message showing
            if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'participant_enabled_closed_caption.png'), confidence=0.9) is not None:
                logging.info("Message for participant has enabled closed caption showing..")
                # try to close window
                x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                            IMG_PATH, 'participant_enabled_closed_caption_close.png'), confidence=0.9)
                pyautogui.click(x, y)
                time.sleep(1)
                if wrap( pyautogui.locateOnScreen, os.path.join(IMG_PATH, 'meeting_chat.png'), confidence=0.9):
                    logging.info("Failed to close message for participant has enabled closed caption...")
                else:
                    logging.info("Successfully closed message for participant has enabled closed caption..")

            time.sleep(self.interval)
       
def check_connecting(zoom_pid, start_date, duration):
    # Check if connecting
    check_periods = 0
    connecting = False
    # Check if connecting
    if wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'connecting.png'), confidence=0.9) is not None:
        connecting = True
        logging.info("Connecting..")

    # Wait while connecting
    # Exit when meeting ends after time
    while connecting:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom_pid), signal.SIGQUIT)
            return

        if wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'connecting.png'), confidence=0.9) is None:
            logging.info("Maybe not connecting anymore..")
            check_periods += 1
            if check_periods >= 2:
                connecting = False
                logging.info("Not connecting anymore..")
                return
        time.sleep(2)


def join_meeting_id(meet_id):
    logging.info("Join a meeting by ID..")
    found_join_meeting = False
    try:
        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'join_meeting.png'), minSearchTime=2, confidence=0.9)
        pyautogui.click(x, y)
        found_join_meeting = True
    except TypeError:
        pass

    if not found_join_meeting:
        logging.error("Could not find 'Join Meeting' on screen!")
        return False

    time.sleep(2)

    # Insert meeting id
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.write(meet_id, interval=0.1)

    # Insert name
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.write(DISPLAY_NAME, interval=0.1)

    # Configure
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('space')

    time.sleep(2)

    return check_error()


def join_meeting_url():
    logging.info("Join a meeting by URL..")

    # Insert name
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.write(DISPLAY_NAME, interval=0.1)

    # Configure
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('space')
    pyautogui.press('tab')
    pyautogui.press('space')

    time.sleep(2)

    return check_error()
    

def check_error():
    # Sometimes invalid id error is displayed
    if wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'invalid_meeting_id.png'), confidence=0.9) is not None:
        logging.error("Maybe a invalid meeting id was inserted..")
        left = False
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, 
                os.path.join(IMG_PATH, 'leave.png'), confidence=0.9)
            pyautogui.click(x, y)
            left = True
        except TypeError:
            pass
            # Valid id

        if left:
            if wrap( pyautogui.locateCenterOnScreen, os.path.join(
                    IMG_PATH, 'join_meeting.png'), confidence=0.9) is not None:
                logging.error("Invalid meeting id!")
                return False
        else:
            return True

    if wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'authorized_attendees_only.png'), confidence=0.9) is not None:
        logging.error("This meeting is for authorized attendees only!")
        return False

    return True


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


def show_toolbars():
    # Mouse move to show toolbar
    width, height = pyautogui.size()
    y = (height / 2)
    pyautogui.moveTo(0, y, duration=0.5)
    pyautogui.moveTo(width - 1, y, duration=0.5)


def join_audio(description):
    audio_joined = False
    try:
        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'join_with_computer_audio.png'), confidence=0.9)
        logging.info("Join with computer audio..")
        pyautogui.click(x, y)
        audio_joined = True
        return True
    except TypeError:
        logging.error("Could not join with computer audio!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_join_with_computer_audio_error.png")
    time.sleep(1)
    if not audio_joined:
        try:
            show_toolbars()
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'join_audio.png'), confidence=0.9)
            pyautogui.click(x, y)
            join_audio(description)
        except TypeError:
            logging.error("Could not join audio!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(

                    TIME_FORMAT) + "-" + description) + "_join_audio_error.png")
            return False


def unmute(description):
    try:
        show_toolbars()
        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'unmute.png'), confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not unmute!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(TIME_FORMAT) + "-" + description) + "_unmute_error.png")
        return False


def mute(description):
    try:
        show_toolbars()
        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'mute.png'), confidence=0.9)
        pyautogui.click(x, y)
        return True
    except TypeError:
        logging.error("Could not mute!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(TIME_FORMAT) + "-" + description) + "_mute_error.png")
        return False


def join(event):
    global VIDEO_PANEL_HIDED
    ffmpeg_debug = None
    
    if int(event[EventField.STATUS.value]) == int(EventStatus.SCHEDULED.value) and not event[EventField.ASSIGNED.value]:
        event[EventField.ASSIGNED.value] = CLIENT_ID
        event[EventField.ASSIGNED_TIMESTAMP.value] = Events.now(event).isoformat()
        try:
            update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
        except Exception as e:
            logging.error(f"Error updating event: {e}")
            return

    meet_id = event[EventField.ID.value]
    meet_pw = event[EventField.PASSWORD.value]
    meet_url = event[EventField.URL.value]
    duration = int(event[EventField.DURATION.value]) * 60
    description = event[EventField.TITLE.value]

    logging.info("Join meeting: " + description)

    if logging.getLogger().level == logging.DEBUG:

        # Start recording
        width, height = pyautogui.size()
        resolution = str(width) + 'x' + str(height)
        disp = os.getenv('DISPLAY')

        logging.debug("Start recording joining process..")

        filename = os.path.join( 
            REC_PATH, time.strftime(TIME_FORMAT)) + "-" + description + "-JOIN.mkv"

        command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
            resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
            " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

        logging.debug(f"Recording command: {command}")

        ffmpeg_debug = subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        
        atexit.register(os.killpg, os.getpgid(
            ffmpeg_debug.pid), signal.SIGQUIT)

    # Exit Zoom if running
    exit_process_by_name("zoom")

    join_by_url = meet_url.startswith('https://') or meet_url.startswith('http://')

    if not join_by_url:
        # Start Zoom
        zoom = subprocess.Popen("zoom", stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        img_name = 'join_meeting.png'
    else:
        logging.info("Starting zoom with url")
        zoom = subprocess.Popen(f'zoom --url="{meet_url}"', stdout=subprocess.PIPE,
                                shell=True, preexec_fn=os.setsid)
        img_name = 'join.png'
    
    # Wait while zoom process is there
    list_of_process_ids = find_process_id_by_name('zoom')
    while len(list_of_process_ids) <= 0:
        logging.info("No Running Zoom Process found!")
        list_of_process_ids = find_process_id_by_name('zoom')
        time.sleep(1)

    # Wait for zoom is started
    loop = True
    useCase = 0 # standard use case
    while (loop):
        if wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, img_name), confidence=0.9):
            loop = False
        else:
           if wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'leave_red.png'), confidence=0.9):
               loop = False
               useCase = UC_CONNECTED_NOPOPUPS

        logging.info("Zoom not ready yet!")
        time.sleep(1)

    logging.info("Zoom started!")
    start_date = datetime.now()

    if not join_by_url:
        joined = join_meeting_id(meet_id)
    else:
        time.sleep(2)
        if useCase == UC_CONNECTED_NOPOPUPS:
            joined = True # there is popup to input display name or anything
        else:
            joined = join_meeting_url()

    if not joined:
        logging.error("Failed to join meeting!")
        os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
        if logging.getLogger().level == logging.DEBUG and ffmpeg_debug is not None:
            # closing ffmpeg
            os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
            atexit.unregister(os.killpg)
        return

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    if not join_by_url:
        pyautogui.write(meet_pw, interval=0.2)
        pyautogui.press('tab')
        pyautogui.press('space')

    # Joined meeting
    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    # Check if meeting is started by host
    check_periods = 0
    meeting_started = True

    time.sleep(2)

    # Check if waiting for host
    if wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'wait_for_host.png'), confidence=0.9, minSearchTime=3) is not None:
        meeting_started = False
        logging.info("Please wait for the host to start this meeting.")

    # Wait for the host to start this meeting
    # Exit when meeting ends after time
    while not meeting_started:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if logging.getLogger().level == logging.DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'wait_for_host.png'), confidence=0.9) is None:
            logging.info("Maybe meeting was started now.")
            check_periods += 1
            if check_periods >= 2:
                meeting_started = True
                logging.info("Meeting started by host.")
                break
        time.sleep(2)

    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    # Check if in waiting room
    check_periods = 0
    in_waitingroom = False

    time.sleep(2)

    # Check if joined into waiting room
    if wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'waiting_room.png'), confidence=0.9,
                                      minSearchTime=3) is not None:
        in_waitingroom = True
        logging.info("Please wait, the meeting host will let you in soon..")

    # Wait while host will let you in
    # Exit when meeting ends after time
    while in_waitingroom:
        if (datetime.now() - start_date).total_seconds() > duration:
            logging.info("Meeting ended after time!")
            logging.info("Exit Zoom!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if logging.getLogger().level == logging.DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            return

        if wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'waiting_room.png'), confidence=0.9) is None:
            logging.info("Maybe no longer in the waiting room..")
            check_periods += 1
            if check_periods == 2:
                logging.info("No longer in the waiting room..")
                break
        time.sleep(2)

    # Meeting joined
    # Check if connecting
    check_connecting(zoom.pid, start_date, duration)

    logging.info("Joined meeting..")

    # Check if recording warning is shown at the beginning
    if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'meeting_is_being_recorded.png'), confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("This meeting is being recorded..")
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'got_it.png'), confidence=0.9)
            pyautogui.click(x, y)
            logging.info("Accepted recording..")
        except TypeError:
            logging.error("Could not accept recording!")

    # Check if host is sharing poll results at the beginning
    if (wrap( pyautogui.locateCenterOnScreen, os.path.join(IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9,
                                       minSearchTime=2) is not None):
        logging.info("Host is sharing poll results..")
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'host_is_sharing_poll_results.png'), confidence=0.9)
            pyautogui.click(x, y)
            try:
                x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                    IMG_PATH, 'exit.png'), confidence=0.9)
                pyautogui.click(x, y)
                logging.info("Closed poll results window..")
            except TypeError:
                logging.error("Could not exit poll results window!")
                if logging.getLogger().level == logging.DEBUG:
                    pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                        TIME_FORMAT) + "-" + description) + "_close_poll_results_error.png")
        except TypeError:
            logging.error("Could not find poll results window anymore!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_find_poll_results_error.png")

    # Start BackgroundThread
    BackgroundThread()

    # Set computer audio
    time.sleep(2)
    if not join_audio(description):
        if not useCase == UC_CONNECTED_NOPOPUPS: 
            logging.info("Exit!")
            os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
            if logging.getLogger().level == logging.DEBUG:
                os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
                atexit.unregister(os.killpg)
            time.sleep(2)
            join(event)

    # 'Say' something if path available (mounted)
    if os.path.exists(AUDIO_PATH):
        play_audio(description)

    time.sleep(2)
    logging.info("Enter fullscreen..")
    show_toolbars()
    try:
        x, y = wrap( pyautogui.locateCenterOnScreen, 
            os.path.join(IMG_PATH, 'view.png'), confidence=0.9)
        pyautogui.click(x, y)
    except TypeError:
        logging.error("Could not find view!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_view_error.png")

    time.sleep(2)

    fullscreen = False
    try:
        x, y = wrap( pyautogui.locateCenterOnScreen, 
            os.path.join(IMG_PATH, 'fullscreen.png'), confidence=0.9)
        pyautogui.click(x, y)
        fullscreen = True
    except TypeError:
        logging.error("Could not find fullscreen!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_fullscreen_error.png")

    # TODO: Check for 'Exit Full Screen': already fullscreen -> fullscreen = True

    # Screensharing already active
    if not fullscreen:
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'view_options.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view options!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_view_options_error.png")

        # Switch to fullscreen
        time.sleep(2)
        show_toolbars()

        logging.info("Enter fullscreen..")
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'enter_fullscreen.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not enter fullscreen by image!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_enter_fullscreen_error.png")
            return

        time.sleep(2)

    # Screensharing not active
    screensharing_active = False
    try:
        x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
            IMG_PATH, 'view_options.png'), confidence=0.9)
        pyautogui.click(x, y)
        screensharing_active = True
    except TypeError:
        logging.error("Could not find view options!")
        if logging.getLogger().level == logging.DEBUG:
            pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                TIME_FORMAT) + "-" + description) + "_view_options_error.png")

    time.sleep(2)

    if screensharing_active:
        # hide video panel
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'hide_video_panel.png'), confidence=0.9)
            pyautogui.click(x, y)
            VIDEO_PANEL_HIDED = True
            logging.info("Video panel hidden successfully..")
        except TypeError:
            logging.error("Could not hide video panel!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_hide_video_panel_error.png")
    else:
        # switch to speaker view
        show_toolbars()

        logging.info("Switch view..")
        try:
            x, y = wrap( pyautogui.locateCenterOnScreen, 
                os.path.join(IMG_PATH, 'view.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not find view!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_view_error.png")

        time.sleep(2)

        try:
            # speaker view
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'speaker_view.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not switch speaker view!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_speaker_view_error.png")

        try:
            # minimize panel
            x, y = wrap( pyautogui.locateCenterOnScreen, os.path.join(
                IMG_PATH, 'minimize.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            logging.error("Could not minimize panel!")
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_minimize_error.png")

    # Move mouse from screen
    pyautogui.moveTo(0, 100)
    pyautogui.click(0, 100)

    if logging.getLogger().level == logging.DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
        atexit.unregister(os.killpg)

    process = Events.get_instruction_attribute( EventInstructionAttribute.PROCESS, event)
    if process == 'record':
        logging.info("Start recording..")

        filename = os.path.join(REC_PATH, time.strftime(
            TIME_FORMAT) + "-" + description) + ".mkv"

        width, height = pyautogui.size()
        resolution = str(width) + 'x' + str(height)
        disp = os.getenv('DISPLAY')

        command = "ffmpeg -nostats -loglevel error -f pulse -ac 2 -i 1 -f x11grab -r 30 -s " + \
            resolution + " " + FFMPEG_INPUT_PARAMS + " -i " + disp + " " + FFMPEG_OUTPUT_PARAMS + \
            " -threads 0 -async 1 -vsync 1 \"" + filename + "\""

        logging.debug(f"Recording command: {command}")

        ffmpeg = subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

        atexit.register(os.killpg, os.getpgid(
            ffmpeg.pid), signal.SIGQUIT)

    # update event
    try:
        event[EventField.STATUS.value] = EventStatus.PROCESS.value
        event[EventField.ASSIGNED_TIMESTAMP.value] = Events.convert_to_local_datetime(datetime.now(), event).isoformat() 
        update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
    except Exception as e:
        logging.error(f"Error updating event: {e}")

    start_date = datetime.now()
    end_date = start_date + timedelta(seconds=duration + TRAIL_TIME_SEC)  # Add 5 minutes

    # Start thread to check active screensharing
    HideViewOptionsThread(description)
        
    meeting_running = True
    while meeting_running:
        time_remaining = end_date - datetime.now()
        if time_remaining.total_seconds() < 0 or not ONGOING_MEETING:
            meeting_running = False
        else:
            print(f"Meeting ends in {time_remaining}", end="\r", flush=True)
        time.sleep(5)

    logging.info("Meeting ends at %s" % datetime.now())

    # Close everything
    if logging.getLogger().level == logging.DEBUG and ffmpeg_debug is not None:
        os.killpg(os.getpgid(ffmpeg_debug.pid), signal.SIGQUIT)
        atexit.unregister(os.killpg)

    os.killpg(os.getpgid(zoom.pid), signal.SIGQUIT)
    os.killpg(os.getpgid(ffmpeg.pid), signal.SIGQUIT)
    atexit.unregister(os.killpg)

    if not ONGOING_MEETING:
        try:
            # Press OK after meeting ended by host
            x, y = wrap( pyautogui.locateCenterOnScreen, 
                os.path.join(IMG_PATH, 'ok.png'), confidence=0.9)
            pyautogui.click(x, y)
        except TypeError:
            if logging.getLogger().level == logging.DEBUG:
                pyautogui.screenshot(os.path.join(DEBUG_PATH, time.strftime(
                    TIME_FORMAT) + "-" + description) + "_ok_error.png")
                
    postprocess = Events.get_instruction_attribute( EventInstructionAttribute.POSTPROCESS, event)  

    if postprocess:
        command = f"./postprocess.sh {postprocess} {filename}"
        logging.debug(f"Postprocess command: {command}")

        postprocess_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
        
        atexit.register(os.killpg, os.getpgid(
            postprocess_process.pid), signal.SIGQUIT)
        
        if postprocess_process:
            logging.info("Starting postprocessing task...")
            event[EventField.STATUS.value] = EventStatus.POSTPROCESS.value
            event[EventField.ASSIGNED.value] = CLIENT_ID
            event[EventField.ASSIGNED_TIMESTAMP.value] = Events.convert_to_local_datetime(datetime.now(), event).isoformat()   
            try:
                update_event_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
            except Exception as e:
                logging.error(f"Error updating event: {e}")

            postprocess_process.wait()
            logging.info("Postprocessing task completed.")

        else:
            logging.error("Postprocessing script not found or not specified.")

    try:
        event[EventField.STATUS.value] = EventStatus.SCHEDULED.value
        event[EventField.ASSIGNED.value] = ''
        event[EventField.ASSIGNED_TIMESTAMP.value] = ''
        update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
    except Exception as e:
        logging.error(f"Error updating event: {e}")

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

    def monitor_events():
        """Monitor and join events based on time windows with local event storage"""
        monitor_events = {}
        max_last_updated_timestamp = None
        # Filter to get only planned events
        filter_type = [EventField.TYPE.value, "=", EventType.ZOOM.value]
        filters = [filter_type, [EventField.STATUS.value, "=", EventStatus.SCHEDULED.value]]

        while True:
            try:
                # Get updates from API
                updated_events = get_event_api(
                    SERVER_URL,
                    SERVER_USERNAME,
                    SERVER_PASSWORD,
                    filters=filters
                )
                
                # Update max timestamp from current batch
                if updated_events:
                    max_last_updated_timestamp = max(event[EventField.LAST_UPDATED_TIMESTAMP.value] for event in updated_events)
                    logging.info(f"events updated: {len(updated_events)} , latest update: {max_last_updated_timestamp}")
                    # Set filter to only get events updated after the latest timestamp (also deleted so we can remove them)
                    filters = [ filter_type, [EventField.LAST_UPDATED_TIMESTAMP.value, ">", max_last_updated_timestamp]]
                
                # Merge updates using dictionary
                for event in updated_events:
                    if event[EventField.STATUS.value] == EventStatus.DELETED.value:
                        # Remove deleted events
                        del monitor_events[event[EventField.KEY.value]]  # Remove entry if exists
                    elif event[EventField.ASSIGNED.value] and event[EventField.ASSIGNED.value] != CLIENT_ID:
                         # events assigned to other clients
                        del monitor_events[event[EventField.KEY.value]]  # Remove entry if exists
                    else:
                        # Add or update event
                        monitor_events[event[EventField.KEY.value]] = event  # Add or update entry
                
                # Process events
                next_event = None
                next_event_dtstart = Events.replaceTimezone( datetime.max)

                for event in monitor_events.values():
                    # Skip assigned events
                    if event[EventField.ASSIGNED.value] != '' and event[EventField.ASSIGNED.value] != CLIENT_ID:
                        continue
                    try:
                        now_in_tz = Events.now( event)

                        max_end_window = Events.replaceTimezone( event, datetime.min)
                        
                        # Check all event occurrences
                        for dtstart in Events.get_dtstart_datetime_list(event, now_in_tz):
                            start_window = dtstart - timedelta(seconds=LEAD_TIME_SEC)
                            end_window = dtstart + timedelta(
                                minutes=int(event[EventField.DURATION.value])) + timedelta(seconds=TRAIL_TIME_SEC)
                            
                            if end_window > max_end_window:
                                max_end_window = end_window
                            
                            if start_window <= now_in_tz <= end_window:
                                logging.info(f"Joining event {event[EventField.KEY.value]} title: '{event[EventField.TITLE.value]}'")
                                join(event)
                                break  # once we return monitoring will continue. One client can only join 1 event
                            elif start_window > now_in_tz and start_window < next_event_dtstart:
                                next_event_dtstart = start_window
                                next_event = event

                        # delte expired events
                        if max_end_window < now_in_tz:  # all events are expired
                            # the event will come through nexrt update as delted and will be removed from monitoring events
                            delete_event_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event_key=event[EventField.KEY.value])
                            
                    except Exception as e:
                        logging.error(f"Event processing error: {str(e)}")
                
                for _ in range(60):
                    if next_event:
                        now_in_tz = Events.now( next_event)
                        print(f"Next event with title: '{next_event[EventField.TITLE.value]}' starts in {next_event_dtstart - now_in_tz}", end="\r", flush=True)
                    else:
                        print(f"No upcoming events (monitoring {len(monitor_events)} events)", end="\r", flush=True)
                    
                    time.sleep(1)
                
            except Exception as e:
                logging.error(f"Monitoring error: {str(e)}")
                print(f"Monitoring error: {str(e)}")

    monitor_events()

if __name__ == '__main__':
    version = get_zoom_version()
    print(f"Zoom version: {version}")
    main()
