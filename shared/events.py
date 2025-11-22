# import csv
from logging import raiseExceptions
import time
import re
import validators
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrulestr
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9
from enum import Enum
import shortuuid
import sqlite3
from .users import UserField
from .constants import DATETIME_FORMAT, STALE_EVENT_THRESHOLD_SECS

# Define constants
INTERNAL_DELIMITER = ',' # don't use : as it is reserved in yaml files

class EventType(Enum):
    ZOOM = 1
    SYSTEM = 2 # used for example to start client in case of manitenance etc

    @classmethod
    def get_description(cls, type):
        return {
            cls.ZOOM.value: "zoom",
            cls.SYSTEM.value: "system"
        }.get(type, "Unknown Type")

class EventInstructionAttribute(Enum):
    PROCESS = "process"
    POSTPROCESS = "postprocess"

class EventStatus(Enum):
    SCHEDULED = 1
    PROCESS = 2
    POSTPROCESS = 3
    ENDED = 4

    @classmethod
    def get_description(cls, status):
        return {
            cls.SCHEDULED.value: "Scheduled",
            cls.PROCESS.value: "Processing",
            cls.POSTPROCESS.value: "Postprocessing",
            cls.ENDED.value: "Ended"
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

class EventInstructionProcess(Enum):
    RECORD = "record"
    JOIN = "join"
class EventInstructionPostprocess(Enum):
    TRANSCRIBE = "transcribe"
    UPLOAD = "upload"
    CUSTOM = "custom"
    ACCESS = "access"

# instructions for process
INSTRUCTION_JOIN_DISPLAY_NAME = "display-name"

# Constants for postprocess instruction keys

# Upload keys
INSTRUCTION_UPLOAD_KEY_DELETE = "delete"

# transcribe keys
INSTRUCTION_TRANSCRIBE_TASK = "task"
INSTRUCTION_TRANSCRIBE_SOURCE_LANGUAGE = "source-language"

# Access configuration keys
INSTRUCTION_ACCESS_HTTP_SERVER = "http-server-access"
INSTRUCTION_ACCESS_KEY = "access-key"
INSTRUCTION_ACCESS_EXPIRE_AFTER_SECONDS = "expire-after-seconds"
INSTRUCTION_ACCESS_NOTIFY_USER = "notify-user"
INSTRUCTION_ACCESS_ADDITIONAL_EMAILS = "additional-emails"

EVENT_DEFAULT_VALUES = {
    EventField.ID.value: '',
    EventField.PASSWORD.value: '',
    EventField.URL.value: '',
    EventField.ASSIGNED.value: '',
    EventField.ASSIGNED_TIMESTAMP.value: '',
    EventField.RRULE.value: '',
    EventField.TYPE.value: EventType.ZOOM.value,
    EventField.STATUS.value: EventStatus.SCHEDULED.value,
    EventField.INSTRUCTION.value: f'{{"{EventInstructionAttribute.PROCESS.value}": [{{"{EventInstructionProcess.RECORD.value}": {{}}}}], "{EventInstructionAttribute.POSTPROCESS.value}": [{{"{EventInstructionPostprocess.TRANSCRIBE.value}": {{}}}}, {{"{EventInstructionPostprocess.UPLOAD.value}": {{"{INSTRUCTION_UPLOAD_KEY_DELETE}": true}}}}]}}'
}

FIELDNAMES = [field.value for field in EventField]

class Events(ABC):
    @abstractmethod
    def create(self, event):
        """Create a new event."""
        pass

    @abstractmethod
    def get(self, filters=None):
        """Retrieve events based on filters. If filters is None, return all events."""
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
    def nameStr(event):
        return f"Event '{event[EventField.TITLE.value]}' with key: '{event[EventField.KEY.value]}'"

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
            duration = event[EventField.DURATION.value]
            try:
                duration = int(duration)
                if duration <= 0:
                    raise ValueError(f"Invalid duration '{duration}'. Duration must be a positive number of minutes.")
            except ValueError:
                raise ValueError(f"Invalid duration '{duration}'. Duration must be a number of minutes.")
        else:
            raise ValueError(f"Missing attribute {EventField.DURATION.value}")
        
        if EventField.RRULE.value in event and event[EventField.RRULE.value]:
            try:
                dtstart_datetime_list = Events.get_dtstart_datetime_list(event)
            except Exception as e:
                raise ValueError(f"Invalid attribute {EventField.RRULE.value} '{event[EventField.RRULE.value]}'. Not a valid RRULE string. {e}")

        if EventField.URL.value in event and event[EventField.URL.value]:
            if event[EventField.URL.value].startswith("http"):
                if not validators.url(event[EventField.URL.value]):
                    raise ValueError(f"Invalid URL format in '{EventField.URL.value}'.")

                # resolve to effective URL address
                # command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event[EventField.ID.value]]
                # result = subprocess.run(command, capture_output=True, text=True)
                # event[EventField.ID.value] = result.stdout.strip()

        # Validate event type if present
        if EventField.TYPE.value in event and event[EventField.TYPE.value] is not None:
            try:
                # Convert type to int if it's a string
                event_type = int(event[EventField.TYPE.value])
                # Check if type is a valid EventType value
                valid_types = [e.value for e in EventType]
                if event_type not in valid_types:
                    valid_types_str = ', '.join(str(t) for t in valid_types)
                    raise ValueError(f"Invalid event type '{event_type}'. Must be one of: {valid_types_str}")
                # Update event with integer type
                event[EventField.TYPE.value] = event_type
            except (ValueError, TypeError) as e:
                raise ValueError(f"Event type must be a number. Got: {event[EventField.TYPE.value]}") from e

        # Validate id if present
        if EventField.ID.value in event and event[EventField.ID.value]:
            if event[EventField.TYPE.value] == EventType.ZOOM.value:  # Use .value for comparison
                if not re.search(r'\d{9,}', event[EventField.ID.value]):
                    raise ValueError("Invalid Zoom id. Must be a number with minimum 9 digits (no blanks)")                

        # Validate status if present
        if EventField.STATUS.value in event and event[EventField.STATUS.value] is not None:
            try:
                # Convert status to int if it's a string
                status = int(event[EventField.STATUS.value])
                # Check if status is a valid EventStatus value
                valid_statuses = [e.value for e in EventStatus]
                if status not in valid_statuses:
                    valid_status_str = ', '.join(str(s) for s in valid_statuses)
                    raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_status_str}")
                # Update event with integer status
                event[EventField.STATUS.value] = status
            except (ValueError, TypeError) as e:
                raise ValueError(f"Status must be a number. Got: {event[EventField.STATUS.value]}") from e

        # Validate instruction
        if EventField.INSTRUCTION.value in event:
            if isinstance(event[EventField.INSTRUCTION.value], str):
                try:
                    for instruction_attribute in EventInstructionAttribute:
                        value = Events.get_instruction_attribute(instruction_attribute, event)
                except Exception as e:
                    raise ValueError(f"Invalid instruction format in '{EventField.INSTRUCTION.value}'. Parsing error for '{event[EventField.INSTRUCTION.value]}': {e.args[0]}")
            else:
                raise ValueError(f"Invalid instruction format in '{EventField.INSTRUCTION.value}'. It must be a string.")
            
        # Validate user
        if EventField.USER_KEY.value in event and event[EventField.USER_KEY.value] != '':
            pass  # User is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {EventField.USER_KEY.value} or it is empty.")

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
            if (fieldname not in event or event[fieldname] is None) and default_value is not None:
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
        dtstart_list = []
        if EventField.RRULE.value in event and event[EventField.RRULE.value]:
            rrule_string = event[EventField.RRULE.value]
            dtfrom = dtfrom if dtfrom else dtstart
            rule = rrulestr(rrule_string, dtstart=dtstart)
            # # for some reason the first date is not included in the rule (despite the inc=True)
            # if dtstart >= dtfrom:
            #     dtstart_list = [dtstart]
            # else:
            #     dtstart_list = []
            # Generate occurrences within a reasonable time frame
            for dt in rule.between(dtstart, dtstart + relativedelta(months=1), inc=True):
                # dt = dt.replace(hour=dtstart.hour, minute=dtstart.minute, second=dtstart.second, microsecond=dtstart.microsecond, tzinfo=dtstart.tzinfo)
                if dt >= dtfrom: # only include occurrences from the future
                    dtstart_list.append(dt)
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
        import json
        if EventField.INSTRUCTION.value in event:
            value = event[EventField.INSTRUCTION.value]
            # Try to parse as JSON
            try:
                obj = json.loads(value)
                if instruction.value in obj:
                    return obj[instruction.value]
            except (json.JSONDecodeError, TypeError) as e:
                raise ValueError(f"Failed to retrieve instruction attribute '{instruction.value}' from instruction '{value}' as it is not valid JSON: {e}")
        return False

class SQLLiteEvents(Events):
    def __init__(self, db_path, stateChanged=None):
        self.db_path = db_path
        self.stateChanged = stateChanged  # Initialize the callback
        self._initialize_db()

    def _get_connection(self):
        """Create and return a database connection with foreign key support enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _initialize_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
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
                        {EventField.CREATED_TIMESTAMP.value} TEXT,
                        {EventField.LAST_UPDATED_TIMESTAMP.value} TEXT,
                        FOREIGN KEY ({EventField.USER_KEY.value}) REFERENCES users({UserField.KEY.value})
                        ON DELETE RESTRICT
                    );
                ''')
                conn.commit()

    def create(self, event):
        event = Events.clean(event)
        event = Events.set_missing_defaults(event)
        event = Events.validate(event)
        event[EventField.KEY.value] = shortuuid.uuid()  # Generate a unique key for the event
        event[EventField.CREATED_TIMESTAMP.value] = Events.now( event).isoformat()
        event[EventField.LAST_UPDATED_TIMESTAMP.value] = event[EventField.CREATED_TIMESTAMP.value]  # Set last updated timestamp

        with self._get_connection() as conn:
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

        # Check for changes and call the callback if necessary
        if self.stateChanged and event:
            self.stateChanged(None, event)
        
        return event
    
    def get(self, filters=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Start building the SQL query
            sql_query = 'SELECT * FROM events'
            conditions = []
            parameters = []

            # Check for filter queries
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
        event[EventField.LAST_UPDATED_TIMESTAMP.value] = Events.now(event).isoformat()

        # retrieve previous event state before update
        pre_event = self.get(filters=[[EventField.KEY.value, "=", event[EventField.KEY.value]]])
        if len(pre_event) == 0:
            raise ValueError(f"Event with key '{event[EventField.KEY.value]}' not found")
        pre_event = pre_event[0]

        with self._get_connection() as conn:
            cursor = conn.cursor()         
            set_clause = ", ".join(f"{field} = ?" for field in event.keys())
            cursor.execute(f'''
                UPDATE events SET {set_clause} WHERE {EventField.KEY.value} = ?
            ''', list(event.values()) + [event[EventField.KEY.value]])
            conn.commit()

        # Check for changes and call the callback if necessary
        if self.stateChanged and pre_event != event:
            self.stateChanged(pre_event, event)

        return event
    
    def delete(self, event_key):
        # retrive previous event state before delete
        pre_event = self.get(filters=[[EventField.KEY.value, "=", event_key]])
        if len(pre_event) == 0:
            raise ValueError(f"Event with key '{event_key}' not found")
        pre_event = pre_event[0]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM events WHERE {EventField.KEY.value} = ?', 
                (event_key,))
            conn.commit()

        # Check for changes and call the callback if necessary
        if self.stateChanged and pre_event:
            self.stateChanged(pre_event, None)

        return True

    def get_next(self, client_id, event_type = None, lead_time_sec=0, trail_time_sec=0):

        statuses = [EventStatus.SCHEDULED.value, EventStatus.PROCESS.value, EventStatus.POSTPROCESS.value, EventStatus.ENDED.value]
        events = []
        for status in statuses:
            filters = []
            if event_type is not None:
                filters.append([EventField.TYPE.value, "=", event_type])
            filters.append([EventField.STATUS.value, "=", status])
            events.extend(self.get(filters=filters))

        # Process events
        next_event = None
        next_event_dtstart = Events.replaceTimezone( datetime.max) # initialize with max date

        for event in events:
            # check stale events
            if event[EventField.ASSIGNED.value] != '' and event[EventField.LAST_UPDATED_TIMESTAMP.value] != '':
                last_updated = datetime.fromisoformat(event[EventField.LAST_UPDATED_TIMESTAMP.value])
                # last_updated = Events.replaceTimezone(last_updated, event[EventField.TIMEZONE.value])
                diff = abs((last_updated - Events.now(event)).total_seconds())

                if diff > STALE_EVENT_THRESHOLD_SECS:
                    # reset stale event
                    event[EventField.ASSIGNED.value] = ''
                    event[EventField.ASSIGNED_TIMESTAMP.value] = ''
                    event[EventField.STATUS.value] = EventStatus.SCHEDULED.value

                    self.update( event)

            # Skip postprocess events
            if event[EventField.STATUS.value] == EventStatus.POSTPROCESS.value:
                continue
                
            # Skip assigned events
            if event[EventField.ASSIGNED.value] != '' and event[EventField.ASSIGNED.value] != client_id:
                continue
            
            dtnow = Events.now( event)

            max_dtend_instance = Events.replaceTimezone( datetime.min) # initialize with min date
            min_dtstart_instance = Events.replaceTimezone( datetime.max) # initialize with max date
            min_dtend_instance = Events.replaceTimezone( datetime.max) # initialize with max date
            
            # Check all event occurrences
            # choose dtfrom such that an instance that has started is included unless it already ended
            dtfrom = dtnow - timedelta(minutes=int(event[EventField.DURATION.value])) - timedelta(seconds=trail_time_sec)
            for dtstart in Events.get_dtstart_datetime_list(event, dtfrom):
                dtstart_instance = dtstart
                dtend_instance = dtstart_instance + timedelta(minutes=int(event[EventField.DURATION.value]))
                if event[EventField.TYPE.value] == EventType.SYSTEM.value:
                    # no lead/trail time for system events
                    dtstart_instance_lead = dtstart_instance
                    dtend_instance_trail = dtend_instance
                else:
                    dtstart_instance_lead = dtstart_instance - timedelta(seconds=lead_time_sec)
                    dtend_instance_trail = dtend_instance + timedelta(seconds=trail_time_sec)
                
                if dtend_instance_trail > max_dtend_instance:
                    max_dtend_instance = dtend_instance_trail
                if dtend_instance_trail < min_dtend_instance:
                    min_dtend_instance = dtend_instance_trail
                if dtstart_instance_lead < min_dtstart_instance:
                    min_dtstart_instance = dtstart_instance_lead

                exclude_ended_instance = False
                if event[EventField.STATUS.value] == EventStatus.ENDED.value: 
                    if dtstart_instance_lead <= dtnow <= dtend_instance_trail:
                        # this event instance has been ended (by host), but still in progress based in schedule
                        # exclude this instance such that we don't join again a already ended instance
                        exclude_ended_instance = True
                
                # if dtstart_instance_lead <= dtnow <= dtend_instance_trail:
                #     next_event = event
                #     break  # we have a meeting that has started
                # elif dtstart_instance_lead > dtnow and dtstart_instance_lead < next_event_dtstart:
                if  dtnow < dtend_instance_trail and \
                    ( event[EventField.STATUS.value] == EventStatus.SCHEDULED.value or \
                      event[EventField.STATUS.value] == EventStatus.PROCESS.value or \
                      event[EventField.STATUS.value] == EventStatus.ENDED.value) and \
                    not exclude_ended_instance and \
                    (next_event is None or dtend_instance_trail < next_event['dtend_instance_trail']):

                    next_event = {}
                    # copy basic event fields
                    next_event[EventField.KEY.value] = event[EventField.KEY.value]
                    next_event[EventField.TITLE.value] = event[EventField.TITLE.value]
                    next_event[EventField.TIMEZONE.value] = event[EventField.TIMEZONE.value]
                    next_event[EventField.TYPE.value] = event[EventField.TYPE.value]
                    next_event[EventField.STATUS.value] = event[EventField.STATUS.value]

                    # copy instance fields
                    next_event['dtstart_instance'] = dtstart_instance
                    next_event['dtend_instance'] = dtend_instance
                    next_event['dtstart_instance_lead'] = dtstart_instance_lead
                    next_event['dtend_instance_trail'] = dtend_instance_trail
                    next_event['dtnow'] = dtnow

            if max_dtend_instance < dtnow:
                # all instances have expired
                if  event[EventField.STATUS.value] == EventStatus.ENDED.value or \
                    event[EventField.STATUS.value] == EventStatus.SCHEDULED.value:
                    self.delete( event_key=event[EventField.KEY.value])
            elif event[EventField.STATUS.value] == EventStatus.ENDED.value and \
                min_dtstart_instance > dtnow and min_dtend_instance > dtnow:
                # a previous instance has ended, but there are future instances
                event[EventField.STATUS.value] = EventStatus.SCHEDULED.value
                self.update( event)

        return next_event