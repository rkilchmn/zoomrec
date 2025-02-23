# import csv
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
import sqlite3
from users import UserField
from constants import DATE_FORMAT, TIME_FORMAT, DATETIME_FORMAT

# Define constants
INTERNAL_DELIMITER = ',' # don't use : as it is reserved in yaml files

class EventType(Enum):
    ZOOM = 1
    SYSTEM = 2 # used for example to start client in case of manitenance etc

class EventInstructionAttribute(Enum):
    PROCESS = "process"
    POSTPROCESS = "postprocess"

class EventStatus(Enum):
    SCHEDULED = 1
    PROCESS = 2
    POSTPROCESS = 3
    DELETED = 99

    @classmethod
    def get_description(cls, status):
        return {
            cls.SCHEDULED: "Scheduled",
            cls.PROCESS: "Processing",
            cls.POSTPROCESS: "Postprocessing",
            cls.DELETED: "Deleted"
        }.get(status, "Unknown Status")

# IMPORTANT: ordering needs to align with table create
class EventField(Enum):
    KEY = 'key'  # Internal technical key for the event
    TYPE = 'type'  # Type of event (e.g., zoom, internal maintenance)
    TITLE = 'title'  # Title of the event
    DTSTART = 'dtstart'  # Start date and time of the event
    TIMEZONE = 'timezone'  # Timezone of the event
    DURATION = 'duration'  # Duration of the event
    RRULE = 'rrule'  # Recurrence rule for the event
    ID = 'id'  # External ID (e.g., Zoom meeting ID)
    PASSWORD = 'password'  # Meeting password
    URL = 'url'  # URL for the event
    INSTRUCTION = 'instruction'  # Instruction for processing the event (e.g., record, transcribe)
    USER_KEY = 'user_key'  # Foreign key referencing the user
    STATUS = 'status'  # Status of the event (e.g., scheduled, processing)
    ASSIGNED = 'assigned'  # Client/worker ID that is processing the event
    ASSIGNED_TIMESTAMP = 'assigned_timestamp'  # Timestamp when the client/worker was assigned
    CREATED_TIMESTAMP = 'created_timestamp'  # Timestamp when the event was created
    LAST_UPDATED_TIMESTAMP = 'last_updated_timestamp'  # Timestamp when the event was last updated

    def __str__(self):
        return self.value

class EventInstruction(Enum):
    RECORD = "record"
    TRANSCRIBE = "transcribe"
    UPLOAD = "upload"

EVENT_DEFAULT_VALUES = {
    EventField.ID.value: '',
    EventField.PASSWORD.value: '',
    EventField.URL.value: '',
    EventField.ASSIGNED.value: '',
    EventField.ASSIGNED_TIMESTAMP.value: '',
    EventField.RRULE.value: '',
    EventField.TYPE.value: EventType.ZOOM.value,
    EventField.STATUS.value: EventStatus.SCHEDULED.value,
    EventField.INSTRUCTION.value: f"{EventInstruction.RECORD.value}"
}

FIELDNAMES = [field.value for field in EventField]

class Events(ABC):
    @abstractmethod
    def create(self, event):
        """Create a new event."""
        pass

    @abstractmethod
    def get(self, event_key=None, filters=None):
        """Retrieve an event by its key or all events if no key is provided."""
        pass

    @abstractmethod
    def update(self, event):
        """Update an existing event."""
        pass

    @abstractmethod
    def delete(self, event_key):
        """Delete an event by its key."""
        pass

    @staticmethod
    def clean(event):
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
    def now(event):
        return datetime.now(ZoneInfo(event[EventField.TIMEZONE.value]))

    @staticmethod
    def find_next(events, leadInSecs=0, leadOutSecs=0):

        next_event = None
        for event in events:
            now = Events.now(event)
            for dtstart in Events.get_dtstart_datetime_list(event):
                try:
                    dtend = dtstart + timedelta(minutes=int(event[EventField.DURATION.value]))
                    # incorporate lead in/out
                    dtstart -= timedelta(seconds=leadInSecs)
                    dtend += timedelta(seconds=leadOutSecs)

                    # priority is given to the meeting ending first - TBD
                    if now < dtend and (next_event is None or dtend < next_event['end']):
                        next_event = event
                        next_event['start'] = dtstart
                        next_event['end'] = dtend
                        next_event['astimezone'] = event[EventField.TIMEZONE.value]
                        next_event['start_astimezone'] = dtstart
                        next_event['end_astimezone'] = dtend

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
                dtstart_datetime_list = Events.get_dtstart_datetime_list(event)
            except ValueError:
                raise ValueError(f"Invalid attribute {EventField.RRULE.value} '{event[EventField.RRULE.value]}'. Not a valid RRULE string.")

        if EventField.URL.value in event and event[EventField.URL.value]:
            if event[EventField.URL.value].startswith("http"):
                if not validators.url(event[EventField.URL.value]):
                    raise ValueError(f"Invalid URL format in '{EventField.URL.value}'.")

                # resolve to effective URL address
                # command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event[EventField.ID.value]]
                # result = subprocess.run(command, capture_output=True, text=True)
                # event[EventField.ID.value] = result.stdout.strip()

         # Validate id 
        if event[EventField.ID.value]:
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
        if EventField.USER_KEY.value in event and event[EventField.USER_KEY.value] != '':
            pass  # User is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {EventField.USER.value} or it is empty.")

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
    def replaceTimezone( dt, timezone="UTC"):
        return dt.replace(tzinfo=ZoneInfo(timezone))

    @staticmethod
    # event datetimes are always in the events (local) timezone
    def get_dtstart_datetime_list(event, dtfrom=None) -> list:
        dtstart = datetime.strptime(event[EventField.DTSTART.value], DATETIME_FORMAT)
        dtstart = Events.replaceTimezone(dtstart, event[EventField.TIMEZONE.value])
        if EventField.RRULE.value in event and event[EventField.RRULE.value]:
            rrule_string = event[EventField.RRULE.value]
            dtfrom = dtfrom if dtfrom else dtstart
            rule = rrulestr(rrule_string, dtstart=dtfrom)
            dtstart_list = [dt for dt in rule]
        else:
            dtstart_list = [dtstart]
        return dtstart_list

    @staticmethod
    def check_past(event, graceSecs=0):
        dtstart_datetime_list = Events.get_dtstart_datetime_list(event)    
        now = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value]))
      
        past_event = True
        for dtstart_datetime in dtstart_datetime_list:
            try:
                end_datetime = dtstart_datetime + timedelta(minutes=int(event[EventField.DURATION.value]))
                end_datetime += timedelta(seconds=graceSecs)
                if end_datetime < now:
                    continue
                else:
                    past_event = False
            except ValueError as e:
                continue
        return past_event

    @staticmethod
    def is_valid_timezone(timezone):
        try:
            ZoneInfo(timezone)
            return True
        except ValueError:
            return False

    @staticmethod
    def find(search_argument, events):
        matching_indices = []
        for i, event in enumerate(events):
            # Check if search_argument is part of any event field's value, handling both strings and integers
            if any(
                (search_argument.lower() in str(event[field.value]).lower() if isinstance(event[field.value], str) else search_argument == str(event[field.value]))
                for field in EventField
            ):
                matching_indices.append(i)
        
        if not matching_indices:
            raise ValueError(f"No event found for '{search_argument}'")
        
        return matching_indices
    
    @staticmethod
    def get_instruction_attribute(instruction: EventInstructionAttribute, event):
        if EventField.INSTRUCTION.value in event:
            entries = event[EventField.INSTRUCTION.value].split(INTERNAL_DELIMITER)
            search_key = f"{instruction.value}="
            for entry in entries:
                if search_key in entry:
                    return entry.split(search_key)[1]
        return False

class SQLLiteEvents(Events):
    def __init__(self, db_path, stateChanged=None):
        self.db_path = db_path
        self.stateChanged = stateChanged  # Initialize the callback
        self._initialize_db()

    def _initialize_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Enable foreign key support
            cursor.execute('PRAGMA foreign_keys = ON;')
            
            # Check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            table_exists = cursor.fetchone()

            # IMPORTANT: order of field needs to align with EventFields order
            if not table_exists:
                cursor.execute(f'''
                    CREATE TABLE events (
                        {EventField.KEY.value} TEXT PRIMARY KEY,
                        {EventField.TYPE.value} INTEGER,
                        {EventField.TITLE.value} TEXT,
                        {EventField.DTSTART.value} TEXT,
                        {EventField.TIMEZONE.value} TEXT,
                        {EventField.DURATION.value} INTEGER,
                        {EventField.RRULE.value} TEXT,
                        {EventField.ID.value} TEXT,
                        {EventField.PASSWORD.value} TEXT,
                        {EventField.URL.value} TEXT,
                        {EventField.INSTRUCTION.value} TEXT,
                        {EventField.USER_KEY.value} TEXT NOT NULL,
                        {EventField.STATUS.value} INTEGER,
                        {EventField.ASSIGNED.value} TEXT,
                        {EventField.ASSIGNED_TIMESTAMP.value} TEXT,
                        {EventField.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        {EventField.LAST_UPDATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY ({EventField.USER_KEY.value}) REFERENCES users({UserField.KEY.value})
                    )
                ''')
                conn.commit()

    def create(self, event):
        event = Events.clean(event)
        event = Events.set_missing_defaults(event)
        event = Events.validate(event)
        event[EventField.KEY.value] = shortuuid.uuid()  # Generate a unique key for the event
        event[EventField.CREATED_TIMESTAMP.value] = datetime.now()  # Set created timestamp
        event[EventField.LAST_UPDATED_TIMESTAMP.value] = event[EventField.CREATED_TIMESTAMP.value]  # Set last updated timestamp

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create a list of field names in the order defined by the EventField enum
            field_names = [field.value for field in EventField]
            field_values = [event[field] for field in field_names]
            
            cursor.execute(f'''
                INSERT INTO events (
                    {", ".join(field_names)}
                ) VALUES ({", ".join("?" for _ in field_names)})
            ''', field_values)  # Use list comprehension to get values in the correct order
            conn.commit()
        
        return event
    
    def get(self, event_key=None, filters=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Start building the SQL query
            sql_query = 'SELECT * FROM events'
            conditions = []
            parameters = []

            # Check for event_key
            if event_key:
                conditions.append(f"{EventField.KEY.value} = ?")
                parameters.append(event_key)

            # Check for additional filter queries
            if filters:
                for filter in filters:
                    if len(filter) == 3:  # Ensure the query has three elements
                        attribute, operator, value = filter
                        if attribute and value is not None:
                            conditions.append(f"{attribute} {operator} ?")
                            parameters.append(value)
                    else:
                        raise ValueError(f"Invalid filter format: {filter}")

            # Combine conditions into the SQL query
            if conditions:
                sql_query += ' WHERE ' + ' AND '.join(conditions)

            cursor.execute(sql_query, parameters)
            rows = cursor.fetchall()
            
            if rows:
                return [{field.value: row[i] for i, field in enumerate(EventField)} for row in rows]
            return []  # Return an empty list if no events are found

    def update(self, event):
        event = Events.clean(event)
        event = Events.validate(event)
        event[EventField.LAST_UPDATED_TIMESTAMP.value] = datetime.now()  # Update last updated timestamp
        old_event = self.get(event[EventField.KEY.value])
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()         
            set_clause = ", ".join(f"{field} = ?" for field in event.keys())
            cursor.execute(f'''
                UPDATE events SET {set_clause} WHERE {EventField.KEY.value} = ?
            ''', list(event.values()) + [event[EventField.KEY.value]])
            conn.commit()

        # Check for changes and call the callback if necessary
        if self.stateChanged and old_event != event:
            self.stateChanged(old_event, event)

        return event
    
    def delete(self, event_key):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'UPDATE events SET status = ?, {EventField.LAST_UPDATED_TIMESTAMP.value} = ? WHERE {EventField.KEY.value} = ?', 
                (EventStatus.DELETED.value, datetime.now(), event_key,))
            conn.commit()

        old_event = self.get(event_key)
        event = {}

        # Check for changes and call the callback if necessary
        if self.stateChanged and old_event != event:
            self.stateChanged(old_event, event)

        return True
