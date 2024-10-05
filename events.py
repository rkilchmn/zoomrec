import csv
import time
import re
import validators
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9
from enum import Enum
import shortuuid

DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
DATETIME_FORMAT = DATE_FORMAT + ' ' + TIME_FORMAT
INTERNAL_DELIMITER = ',' # don't use : as it is reserved in yaml files

class EventType(Enum):
    ZOOM = 1
    SYSTEM = 2 # used for example to start client in case of manitenance etc

class EventInstructionAttribute(Enum):
    RECORD = "record"
    POSTPROCESS = "postprocess"

class EventUserAttribute(Enum):
    TELEGRAM_CHAT_ID = "telegram_chat_id"

class EventStatus(Enum):
    SCHEDULED = 1
    JOINED = 2
    PROCESS = 3
    POSTPROCESS = 4

    @classmethod
    def get_description(cls, status):
        return {
            cls.SCHEDULED: "Scheduled",
            cls.JOINED: "Joined",
            cls.PROCESS: "Processing",
            cls.POSTPROCESS: "Postprocessing"
        }.get(status, "Unknown Status")

class EventField(Enum):
    KEY = 'key' # internal technical key
    TYPE = 'type' # tpe of event e.g. zoom or internal maintenance
    TITLE = 'title'
    DTSTART = 'dtstart' # day and time of event start
    TIMEZONE = 'timezone'
    DURATION = 'duration'
    RRULE = 'rrule' # repetition rule 
    ID = 'id' # external id eg zoom meeting id or zoom link url 
    PASSWORD = 'password' # meeting password
    URL = 'url'
    INSTRUCTION = 'instruction' # what instruction for processing e.g. record, trancribe, upload
    USER = 'user' # user information to allow notifing or providing access
    STATUS = 'status'
    ASSIGNED = 'assigned' # client/worker id that is processing the event
    ASSIGNED_TIMESTAMP = 'assigned_timestamp' # timestamp when client/worker has assigned himself. Will be used for stale reords if worker died

    def __str__(self):
        return self.value

EVENT_DEFAULT_VALUES = {
    EventField.ASSIGNED.value: '',
    EventField.ASSIGNED_TIMESTAMP.value: '',
    EventField.TYPE.value: EventType.ZOOM.value,
    EventField.STATUS.value: EventStatus.SCHEDULED.value
}

FIELDNAMES = [field.value for field in EventField]

class Events(ABC):
    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def write(self, events):
        pass

    @staticmethod
    def clean_event(event):
        clean_event = {}
        for field in EventField:
            if field.value in event:
                clean_event[field.value] = event[field.value]
        return clean_event

    @staticmethod
    def convert_to_safe_filename(filename):
        invalid_chars = '\\/:*?"<>|'
        safe_filename = ''.join(char for char in filename if char not in invalid_chars)
        safe_filename = safe_filename.strip()
        safe_filename = safe_filename.replace(' ', '_')
        if not safe_filename:
            safe_filename = '_'
        safe_filename = safe_filename[:255]
        return safe_filename

    @staticmethod
    def remove_past(events, graceSecs=0):
        filtered_events = []
        for event in events:
            if not Events.check_past(event, graceSecs):
                filtered_events.append(event)
        return filtered_events

    @staticmethod
    def find_next(events, astimezone, leadInSecs=0, leadOutSecs=0):
        now = datetime.now(ZoneInfo(astimezone))
        next_event = None
        for event in events:
            for dtstart_local in Events.get_dtstart_datetime_list(event):
                try:
                    dtend_local = dtstart_local + timedelta(minutes=int(event[EventField.DURATION.value]))
                    # converted to astimezone provided 
                    dtstart_timezone = Events.convert_to_timezone(dtstart_local, ZoneInfo(astimezone))
                    dtend_timezone =  Events.convert_to_timezone(dtend_timezone, ZoneInfo(astimezone))

                    # incorporate lead in/out
                    dtstart_timezone -= timedelta(seconds=leadInSecs)
                    dtend_timezone += timedelta(seconds=leadOutSecs)

                    # priority is given to the meeting ending first - TBD
                    if now < dtend_timezone and (next_event is None or dtend_timezone < next_event['end']):
                        next_event = event
                        next_event['start'] = dtstart_local
                        next_event['end'] = dtend_local
                        next_event['astimezone'] = astimezone
                        next_event['start_astimezone'] = dtstart_timezone
                        next_event['end_astimezone'] = dtend_timezone

                except ValueError as e:
                    continue
        return next_event

    @staticmethod
    def validate(event):
        if event[EventField.DTSTART.value]:
            try:
                time.strptime(event[EventField.DTSTART.value], DATETIME_FORMAT)
            except ValueError:
                raise ValueError(f"Invalid date/time format '{event[EventField.DTSTART.value]}'. Use {DATETIME_FORMAT} format.")
        else:
            raise ValueError(f"Missing attribute {EventField.DTSTART.value}.")

        if event[EventField.TIMEZONE.value]:
            # Validate timezone
            try:
                ZoneInfo(event[EventField.TIMEZONE.value])
            except ValueError:
                raise ValueError(f"Invalid timezone'{event[EventField.TIMEZONE.value]}'. Use values such as 'America/New_York'.")
        else:
            raise ValueError(f"Missing attribute {EventField.TIMEZONE.value}.")

        if event[EventField.DURATION.value]:
            try:
                duration = int(event[EventField.DURATION.value])
                if duration <= 0:
                    raise ValueError(f"Invalid duration '{duration}'. Duration must be a positive number of minutes.")
            except ValueError:
                raise ValueError(f"Invalid duration '{duration}'. Duration must be a number of minutes.")
        else:
            raise ValueError(f"Missing attribute {EventField.DURATION.value}")
        
        if EventField.RRULE.value in event and event[EventField.RRULE.value]:
            try:
                dtstart_datetime_local_list = Events.get_dtstart_datetime_list(event)
            except ValueError:
                raise ValueError(f"Invalid attribute {EventField.RRULE.value} '{event[EventField.RRULE.value]}'. Not a valid RRULE string.")

        if event[EventField.URL.value]:
            if event[EventField.URL.value].startswith("http"):
                if not validators.url(event[EventField.URL.value]):
                    raise ValueError(f"Invalid URL format in '{EventField.URL.value}'.")

                # resolve to effective URL address
                # command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event[EventField.ID.value]]
                # result = subprocess.run(command, capture_output=True, text=True)
                # event[EventField.ID.value] = result.stdout.strip()

         # Validate id 
        if event[EventField.URL.value]:
                if event[EventField.TYPE.value] == EventType.ZOOM:
                    if not re.search(r'\d{9,}', event[EventField.ID.value]):
                        raise ValueError("Invalid Zoom id. Must be a number with minimum 9 digits (no blanks)")                

        # Validate instruction
        if EventField.INSTRUCTION.value in event:
            if isinstance(event[EventField.INSTRUCTION.value], str):
                try:
                    for instruction_attribute in EventInstructionAttribute:
                        value = Events.get_instruction_attribute( instruction_attribute, event)
                except Exception as e:
                    raise ValueError(f"Invalid instruction format in '{EventField.INSTRUCTION.value}'. Parsing error for '{event[EventField.INSTRUCTION.value]}': {e.error.args[0]}")

            else:
                raise ValueError(f"Invalid instruction format in '{EventField.INSTRUCTION.value}'. It must be a string.")
            
        # Validate user
        if EventField.USER.value in event:
            if isinstance(event[EventField.USER.value], str):
                try:
                    for user_attribute in EventUserAttribute:
                        value = Events.get_user_attribute( user_attribute, event)
                except Exception as e:
                    raise ValueError(f"Invalid user format in '{EventField.USER.value}'. Parsing error for '{event[EventField.USER.value]}': {e.error.args[0]}")

            else:
                raise ValueError(f"Invalid user format in '{EventField.USER.value}'. It must be a string.")

    
        # validate if in past
        if Events.check_past(event):
            raise ValueError("Event end date/time is in past.")

        if event.get(EventField.ASSIGNED.value) or event.get(EventField.ASSIGNED_TIMESTAMP.value):
            if  not (event.get(EventField.ASSIGNED.value) or event.get(EventField.ASSIGNED_TIMESTAMP.value)):
                raise ValueError(f"If any of the both Field '{EventField.ASSIGNED_TIMESTAMP}' and '{EventField.ASSIGNED}' are provided, both have to be provided.")

        return event

    @staticmethod
    def generate_unique_id(length=22):
        return shortuuid.ShortUUID().uuid()[:length]

    @staticmethod
    def set_missing_defaults(event):
        for fieldname, default_value in EVENT_DEFAULT_VALUES.items():
            if fieldname not in event and default_value is not None:
                event[fieldname] = default_value
        return event

    @staticmethod
    # event datetimes are always in the events (local) timezone
    def get_dtstart_datetime_list(event):
        dtstart = datetime.strptime(event[EventField.DTSTART.value], DATETIME_FORMAT)
        dtstart_local = dtstart.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
        if EventField.RRULE.value in event and event[EventField.RRULE.value]:
            rrule_string = event[EventField.RRULE.value]
            rule = rrulestr(rrule_string, dtstart=dtstart_local)
            dtstart_list = [dt for dt in rule]
        else:
            dtstart_list = [dtstart_local]
        return dtstart_list

    @staticmethod
    def check_past(event, graceSecs=0):
        dtstart_datetime_local_list = Events.get_dtstart_datetime_list(event)    
        now_local = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value]))
      
        past_event = True
        for dtstart_datetime_local in dtstart_datetime_local_list:
            try:
                end_datetime_local = dtstart_datetime_local + timedelta(minutes=int(event[EventField.DURATION.value]))
                end_datetime_local += timedelta(seconds=graceSecs)
                if end_datetime_local < now_local:
                    continue
                else:
                    past_event = False
            except ValueError as e:
                continue
        return past_event

    @staticmethod
    def convert_to_system_datetime(datetime_local):
        return datetime_local.astimezone(datetime.now().astimezone().tzinfo)
    
    @staticmethod
    def convert_to_timezone(datetime_local, timezone):
        return datetime_local.astimezone(datetime.now().timezone().tzinfo)

    @staticmethod
    def convert_to_local_datetime(datetime_system, event):
        return datetime_system.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))

    @staticmethod
    def is_valid_timezone(timezone):
        try:
            ZoneInfo(timezone)
            return True
        except ValueError:
            return False

    @staticmethod
    def find(search_argument, events):
        try:
            target_index = int(search_argument) - 1
            return target_index
        except ValueError:
            hits = 0
            for i, event in enumerate(events):
                if search_argument in event[EventField.TITLE.value].lower():
                    target_index = i
                    hits += 1
            if hits > 1:
                raise ValueError(f"{hits} event found with description '{search_argument}'. Please make it unique such that only 1 event matches.")
            elif hits == 0:
                raise ValueError(f"No event found with description or index '{search_argument}'")
            elif hits == 1:
                return target_index
    
    @staticmethod
    def get_instruction_attribute(instruction: EventInstructionAttribute, event):
        if EventField.INSTRUCTION.value in event:
            entries = event[EventField.INSTRUCTION.value].split(INTERNAL_DELIMITER)
            search_key = f"{instruction.value}="
            for entry in entries:
                if search_key in entry:
                    return entry.split(search_key)[1]
        return False
    
    @staticmethod
    def get_user_attribute(user_attribute: EventUserAttribute, event):
        if EventField.USER.value in event:
            entries = event[EventField.USER.value].split(INTERNAL_DELIMITER)
            search_key = f"{user_attribute.value}="
            for entry in entries:
                if search_key in entry:
                    return entry.split(search_key)[1]
        return False

class CSVEvents(Events):
    def __init__(self, csv_path, delimiter=';', stateChanged=None):
        self.csv_path = csv_path
        self.delimiter = delimiter
        self.stateChanged = stateChanged  # Initialize the callback

    def read(self):
        events = []
        with open(self.csv_path, 'r') as file:
            reader = csv.reader(file, delimiter=self.delimiter)
            try:
                headers = next(reader)
            except StopIteration:  # Handle empty file/not even header
                return []
            for row in reader:
                event = {headers[i]: row[i] for i in range(len(headers))}
                events.append(event)
        return events

    def write(self, events):
        old_events = self.read()
        old_events = self.remove_past(old_events)
        old_events_dict = {event[EventField.KEY.value]: event for event in old_events}

        with open(self.csv_path, 'w', newline='') as file:
            writer = csv.DictWriter(file, FIELDNAMES, delimiter=self.delimiter)
            writer.writeheader()
            for event in events:
                event = self.set_missing_defaults(event)
                if EventField.KEY.value not in event:  # no key defined yet
                    event[EventField.KEY.value] = self.generate_unique_id()
                writer.writerow(event)

                # Check for changes and call the callback if necessary
                old_event = old_events_dict.get(event[EventField.KEY.value])
                if old_event and self.stateChanged and old_event != event:
                    self.stateChanged(old_event, event)