import csv
import time
import re
import validators
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9
from enum import Enum
import shortuuid

DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
RECORD = 'true'

TELEGRAM_CHAT_ID_KEY = "telegram-chatid"

class EventType(Enum):
    ZOOM = 1
    SYSTEM = 2 # used for example to start client in case of manitenance etc

class EventStatus(Enum):
    SCHEDULED = 1
    JOINED = 2
    RECORDING = 3
    POSTPROCESSING = 4

    @classmethod
    def get_description(cls, status):
        return {
            cls.SCHEDULED: "Scheduled",
            cls.JOINED: "Joined",
            cls.RECORDING: "Recording",
            cls.POSTPROCESSING: "Postprocessing"
        }.get(status, "Unknown Status")

class EventField(Enum):
    KEY = 'key'
    TYPE = 'type'
    STATUS = 'status'
    ASSIGNED = 'assigned'
    ASSIGNED_TIMESTAMP = 'assigned_timestamp'
    POSTPROCESSING = 'postprocessing'
    WEEKDAY = 'weekday'
    TIME = 'time'
    DURATION = 'duration'
    ID = 'id'
    PASSWORD = 'password'
    DESCRIPTION = 'description'
    RECORD = 'record'
    TIMEZONE = 'timezone'
    USER = 'user'

    def __str__(self):
        return self.value

EVENT_DEFAULT_VALUES = {
    EventField.ASSIGNED.value: '',
    EventField.ASSIGNED_TIMESTAMP.value: '',
    EventField.TYPE.value: EventType.ZOOM.value,
    EventField.STATUS.value: EventStatus.SCHEDULED.value,
    EventField.POSTPROCESSING.value: "transcribe",
}

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
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
            for day in Events.expand_days(event["weekday"]):
                try:
                    # in local timezone of event   
                    start_datetime_local = Events.get_local_start_datetime(day, event)
                    end_datetime_local = start_datetime_local + timedelta(minutes=int(event[EventField.DURATION.value]))
                    # converted to astimezone provided 
                    start_datetime = start_datetime_local.astimezone(ZoneInfo(astimezone))
                    end_datetime = end_datetime_local.astimezone(ZoneInfo(astimezone))

                    # incorporate lead in/out
                    start_datetime -= timedelta(seconds=leadInSecs)
                    end_datetime += timedelta(seconds=leadOutSecs)

                    # priority is given to the meeting ending first - TBD
                    if now < end_datetime and (next_event is None or end_datetime < next_event['end']):
                        next_event = event
                        next_event['start'] = start_datetime_local
                        next_event['end'] = end_datetime_local
                        next_event['astimezone'] = astimezone
                        next_event['start_astimezone'] = start_datetime
                        next_event['end_astimezone'] = end_datetime

                except ValueError as e:
                    continue
        return next_event

    @staticmethod
    def validate(event):
        if event[EventField.DESCRIPTION.value]:
            event[EventField.DESCRIPTION.value] = Events.convert_to_safe_filename(event[EventField.DESCRIPTION.value])

        if event[EventField.WEEKDAY.value]:
            try:
                days = Events.expand_days(event[EventField.WEEKDAY.value])
            except ValueError:
                raise ValueError(f"Invalid weekday or date '{event[EventField.WEEKDAY.value]}'. List and ranges of weekdays e.g. monday, tuesday or dates in {DATE_FORMAT} format are supported")
        else:
            raise ValueError("Missing attribute weekday.")

        if event[EventField.TIME.value]:
            # Validate time
            try:
                time.strptime(event[EventField.TIME.value], TIME_FORMAT)
            except ValueError:
                raise ValueError(f"Invalid time format '{event[EventField.TIME.value]}'. Use HH:MM format.")
        else:
            raise ValueError("Missing attribute time.")

        if event[EventField.TIMEZONE.value]:
            # Validate timezone
            try:
                ZoneInfo(event[EventField.TIMEZONE.value])
            except ValueError:
                raise ValueError(f"Invalid timezone'{event[EventField.TIMEZONE.value]}'. Use values such as 'America/New_York'.")
        else:
            raise ValueError("Missing attribute timezone.")

        if event[EventField.DURATION.value]:
            # Validate duration
            try:
                duration = int(event[EventField.DURATION.value])
                if duration <= 0:
                    raise ValueError(f"Invalid duration '{duration}'. Duration must be a positive number of minutes.")
            except ValueError:
                raise ValueError(f"Invalid duration '{duration}'. Duration must be a number of minutes.")
        else:
            raise ValueError("Missing attribute duration")

        # Validate id
        if event[EventField.ID.value]:
            if event[EventField.ID.value].startswith("http"):
                if not validators.url(event[EventField.ID.value]):
                    raise ValueError("Invalid URL format.")

                # resolve to effective URL address
                # command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event[EventField.ID.value]]
                # result = subprocess.run(command, capture_output=True, text=True)
                # event[EventField.ID.value] = result.stdout.strip()

            else:    
                if not re.search(r'\d{9,}', event[EventField.ID.value]):
                    raise ValueError("Invalid id. If id starts with 'https://' then it must be a URL, otherwise it must be a number with minimum 9 digits (no blanks)")                
                if not event[EventField.PASSWORD.value]:
                    raise ValueError("Password cannot be empty.")
        else:
            raise ValueError("Missing attribute id.")

        # Validate record
        if event[EventField.RECORD.value]:
            if event[EventField.RECORD.value] not in ["true", "false"]:
                raise ValueError(f"Invalid record '{event[EventField.RECORD.value]}'. Record must be either 'true' or 'false'")
        else:
            raise ValueError("Missing attribute record.")

        if event.get(EventField.ASSIGNED.value) is not None:
            if event.get(EventField.ASSIGNED_TIMESTAMP.value) is None:
                raise ValueError("ASSIGNED_TIMESTAMP cannot be blank if ASSIGNED is provided.")

        # validate if in past
        if Events.check_past(event):
            raise ValueError("Event end date/time is in past.")

        if event.get(EventField.ASSIGNED.value) is not None:
            if not event.get(EventField.ASSIGNED_TIMESTAMP.value):
                raise ValueError("ASSIGNED_TIMESTAMP cannot be blank if ASSIGNED is provided.")

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
    def now_system_datetime():
        current_datetime = datetime.now()
        current_datetime = current_datetime.astimezone(datetime.now().astimezone().tzinfo) # with system timezone
        return current_datetime

    @staticmethod
    def get_date(weekday, description):
        try:
            event_date = datetime.strptime(weekday, DATE_FORMAT)
            return event_date.strftime(DATE_FORMAT)
        except ValueError:
            pass  # not a valid date, continue with weekday check

        # Check if input is a weekday
        if weekday in WEEKDAYS:
            target_date = datetime.now()
            while target_date.strftime("%A").lower() != weekday.lower():
                target_date += timedelta(days=1)
            return target_date.strftime(DATE_FORMAT)
        else:
            raise ValueError("Invalid date/weekday {} in {}.".format(weekday, description))

    @staticmethod
    def expand_days(days_str):
        days_list = []
        list_parts = days_str.split(',')
        for part in list_parts:
            range_parts = part.split('-')
            if len(range_parts) == 1:
                if part.lower() in WEEKDAYS:
                    days_list.append(part.lower())
                else:
                    try:
                        date = datetime.strptime(part, DATE_FORMAT).date()
                        days_list.append(date.strftime(DATE_FORMAT))
                    except ValueError:
                        pass
            elif len(range_parts) == 2:
                if range_parts[0].lower() in WEEKDAYS and range_parts[1].lower() in WEEKDAYS:
                    start_index = WEEKDAYS.index(range_parts[0].lower())
                    end_index = WEEKDAYS.index(range_parts[1].lower())
                    WEEKDAYS_range = WEEKDAYS[start_index:end_index + 1]
                    days_list.extend(WEEKDAYS_range)
                else:
                    try:
                        start_date = datetime.strptime(range_parts[0], DATE_FORMAT).date()
                        end_date = datetime.strptime(range_parts[1], DATE_FORMAT).date()
                        dates_range = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
                        days_list.extend([date.strftime(DATE_FORMAT) for date in dates_range])
                    except ValueError:
                        pass
        return days_list

    @staticmethod
    def check_past(event, graceSecs=0):
        now = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value]))
        past_event = True
        for day in Events.expand_days(event["weekday"]):
            if day in WEEKDAYS: # weekdays are recurring events
                past_event = False
            else:
                try:
                    start_date_str = Events.get_date(day, event[EventField.DESCRIPTION.value])
                    start_datetime = datetime.strptime(start_date_str + ' ' + event[EventField.TIME.value], DATE_FORMAT + ' ' + TIME_FORMAT)
                    start_datetime = start_datetime.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
                    end_datetime = start_datetime + timedelta(minutes=int(event[EventField.DURATION.value]))
                    end_datetime += timedelta(seconds=graceSecs)
                    if end_datetime < now:
                        continue
                    else:
                        past_event = False
                except ValueError as e:
                    continue
        return past_event   

    @staticmethod
    def get_local_start_datetime(day, event): 
        start_date_str = Events.get_date(day, event[EventField.DESCRIPTION.value])
        start_datetime = datetime.strptime(start_date_str + ' ' + event[EventField.TIME.value], DATE_FORMAT + ' ' + TIME_FORMAT)  
        start_datetime = start_datetime.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
        return start_datetime

    @staticmethod
    def convert_to_system_datetime(datetime_local):
        return datetime_local.astimezone(datetime.now().astimezone().tzinfo)

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
                if search_argument in event[EventField.DESCRIPTION.value].lower():
                    target_index = i
                    hits += 1
            if hits > 1:
                raise ValueError(f"{hits} event found with description '{search_argument}'. Please make it unique such that only 1 event matches.")
            elif hits == 0:
                raise ValueError(f"No event found with description or index '{search_argument}'")
            elif hits == 1:
                return target_index

    @staticmethod
    def set_telegramchatid(chat_id):
        return "{TELEGRAM_CHAT_ID_KEY}={}".format(chat_id)

    @staticmethod
    def get_telegramchatid(user):
        entries = user.split(":")
        search_key = f"{TELEGRAM_CHAT_ID_KEY}="
        for entry in entries:
                if search_key in entry:
                    chat_id = entry.split(search_key)[1]
                return chat_id
        return None 

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