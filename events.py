import csv
import time
import re
import validators
# import subprocess # to run curl
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9


CSV_DELIMITER = ";"

DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
RECORD = 'true'


WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
FIELDNAMES =['weekday', 'time', 'duration', 'id', 'password', 'description', 'record','timezone', 'user']

def now_system_datetime():
    current_datetime = datetime.now()
    current_datetime = current_datetime.astimezone(datetime.now().astimezone().tzinfo) # with system timezone

    return current_datetime


def getDate(weekday, description):
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


def convert_to_safe_filename(filename):
    # Define a set of characters that are not allowed in SMB filenames
    # Reference: https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions
    invalid_chars = '\\/:*?"<>|'

    # Remove any invalid characters from the filename
    safe_filename = ''.join(char for char in filename if char not in invalid_chars)

    # Remove any leading or trailing spaces
    safe_filename = safe_filename.strip()

    # Replace any remaining spaces with underscores
    safe_filename = safe_filename.replace(' ', '_')

    # Ensure that the resulting filename is not empty
    if not safe_filename:
        safe_filename = '_'

    # Limit the filename length to 255 characters (maximum allowed by SMB)
    safe_filename = safe_filename[:255]

    return safe_filename


def expand_days(days_str):
    days_list = []

    # Split the input string by ',' to get individual parts
    list_parts = days_str.split(',')

    # Loop through each part
    for part in list_parts:
        # Split the part by '-' to check for ranges
        range_parts = part.split('-')

        # If the part has a single value
        if len(range_parts) == 1:
            # Check if it's a weekday
            if part.lower() in WEEKDAYS:
                days_list.append(part.lower())  # Append the weekday
            else:
                # If it's not a weekday, try to parse it as a date
                try:
                    date = datetime.strptime(part, DATE_FORMAT).date()
                    days_list.append(date.strftime(DATE_FORMAT))  # Append the formatted date
                except ValueError:
                    pass  # Ignore if it's not a valid date or weekday

        # If the part has two values (range)
        elif len(range_parts) == 2:
            # Check if both parts are WEEKDAYS
            if range_parts[0].lower() in WEEKDAYS and range_parts[1].lower() in WEEKDAYS:
                # Get the index of the start and end WEEKDAYS in the WEEKDAYS list
                start_index = WEEKDAYS.index(range_parts[0].lower())
                end_index = WEEKDAYS.index(range_parts[1].lower())

                # Get the WEEKDAYS between the start and end WEEKDAYS (inclusive)
                WEEKDAYS_range = WEEKDAYS[start_index:end_index + 1]

                # Append the WEEKDAYS to the days_list
                days_list.extend(WEEKDAYS_range)
            else:
                # If not both WEEKDAYS, try to parse as dates
                try:
                    start_date = datetime.strptime(range_parts[0], DATE_FORMAT).date()
                    end_date = datetime.strptime(range_parts[1], DATE_FORMAT).date()

                    # Get the dates between the start and end dates (inclusive)
                    dates_range = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

                    # Append the formatted dates to the days_list
                    days_list.extend([date.strftime(DATE_FORMAT) for date in dates_range])
                except ValueError:
                    pass  # Ignore if it's not a valid date or weekday

    return days_list


def read_events_from_csv(file_name):
    global CSV_DELIMITER
    events = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file,delimiter=CSV_DELIMITER)
        headers = next(reader)
        for row in reader:
            event = {headers[i]: row[i] for i in range(len(headers))}
            events.append(event)
    return events

def write_events_to_csv(file_name, events):
    global CSV_DELIMITER
    with open(file_name, 'w', newline='') as file:
        writer = csv.DictWriter(file, FIELDNAMES, delimiter=CSV_DELIMITER)
        writer.writeheader()
        for event in events:
            writer.writerow(event)

def find_next_event(events, astimezone, leadInSecs = 0, leadOutSecs = 0):
    now = datetime.now(ZoneInfo(astimezone))
    next_event = None
    for event in events:
        for day in expand_days(event["weekday"]):
            try:
                # in local timezone of event   
                start_datetime_local = get_next_event_local_start_datetime( day, event)
                end_datetime_local = start_datetime_local + timedelta(minutes=int(event['duration']))
                # converted to astimezone provided 
                start_datetime = start_datetime_local.astimezone(ZoneInfo(astimezone))
                end_datetime = end_datetime_local.astimezone(ZoneInfo(astimezone))

                # incorparate lead in/out
                start_datetime -= timedelta(seconds=leadInSecs)
                end_datetime += timedelta(seconds=leadOutSecs)

                # prioriy is given to the meeting ending first - TBD
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

def check_past_event(event, graceSecs=0):
    now = datetime.now(ZoneInfo(event['timezone']))
    past_event = True
    for day in expand_days(event["weekday"]):
        if day in WEEKDAYS: # weekdays are recurring events
            past_event = False
        else:
            try:
                start_date_str = getDate(day, event['description'])
                start_datetime = datetime.strptime(start_date_str + ' ' + event['time'], DATE_FORMAT + ' ' + TIME_FORMAT)
                end_datetime = start_datetime + timedelta(minutes=int(event['duration']))
                end_datetime = end_datetime.astimezone(ZoneInfo(event['timezone']))
                end_datetime += timedelta(seconds=graceSecs)
                # Check if the event has ended
                if end_datetime < now:
                    continue
                else:
                    past_event = False
            except ValueError as e:
                continue
    return past_event   

def remove_past_events(events, graceSecs=0):  
    filtered_events = []
    for event in events:
        if not check_past_event(event, graceSecs):
            filtered_events.append( event)       
    return filtered_events

# datetime of event start in the events local timezone
def get_next_event_local_start_datetime( day, event): 
    start_date_str = getDate( day, event['description'])
    start_datetime = datetime.strptime(start_date_str + ' ' + event['time'], DATE_FORMAT + ' ' + TIME_FORMAT)  
    start_datetime = start_datetime.replace(tzinfo=ZoneInfo(event['timezone']))

    return start_datetime

def convert_to_system_datetime( datetime_local ):
    return datetime_local.astimezone(datetime.now().astimezone().tzinfo)

def is_valid_timezone(timezone):
    # Validate timezone
        try:
           ZoneInfo(timezone)
           return True
        except ValueError:
            return False

def validate_event(event):
    if event['description']:
        event['description'] = convert_to_safe_filename(event['description'])
    
    if event['weekday']:
        try:
            days = expand_days(event['weekday'])
        except ValueError:
            raise ValueError(f"Invalid weekday or date '{event['weekday']}'. List and ranges of weekays e.g. monday, tuesday or dates in {DATE_FORMAT} format are supported")
    else:
        raise ValueError("Missing attribute weekday.")

    if event['time']:
        # Validate time
        try:
            time.strptime(event['time'], TIME_FORMAT)
        except ValueError:
            raise ValueError(f"Invalid time format '{event['time']}'. Use HH:MM format.")
    else:
        raise ValueError("Missing attribute time.")
    
    if event['timezone']:
        # Validate timezone
        try:
           ZoneInfo(event['timezone'])
        except ValueError:
            raise ValueError(f"Invalid timezone'{event['timezone']}'. Use values such as 'America/New_York'.")
    else:
        raise ValueError("Missing attribute timezone.")
    
    if event['duration']:
    # Validate duration
        try:
            duration = int(event['duration'])
            if duration <= 0:
                raise ValueError(f"Invalid duration '{duration}'. Duration must be a positive number of minutes.")
        except ValueError:
            raise ValueError(f"Invalid duration '{duration}'. Duration must be a number of minutes.")
    else:
        raise ValueError("Missing attribute duration")
            
    # Validate id
    if event['id']:
        if event['id'].startswith("http"):
            if not validators.url(event['id']):
                raise ValueError("Invalid URL format.")
            
            # resolve to effective URL address
            # command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event['id']]
            # result = subprocess.run(command, capture_output=True, text=True)
            # event['id'] = result.stdout.strip()
            
        else:    
            if not re.search( r'\d{9,}', event['id']):
                raise ValueError("Invalid id. If id starts with 'https://' then it must be a URL, otherwise it must be a number with minimum 9 digits (no blanks)")                
            if not event['password']:
                raise ValueError("Password cannot be empty.")
    else:
        raise ValueError("Missing attribute id.")

    # Validate record
    if event['record']:
        if event['record'] not in ["true", "false"]:
            raise ValueError(f"Invalid record '{event['record']}'. Record must be either 'true' or 'false'")
    else:
        raise ValueError("Missing attribute record.")
    
    # validate if in past
    if check_past_event( event):
        raise ValueError("Event end date/time is in past.")
    
    return event

def find_event( search_argument, events):
    try:
        # Try to interpret the argument as an index
        target_index = int(search_argument) - 1
        return target_index
    except ValueError:
        # If it's not an index, search for an event whose description contains the argument
        hits = 0
        for i, event in enumerate(events):
            if search_argument in event['description'].lower():
                target_index = i
                hits += 1

        if hits > 1:
            raise ValueError(f"{hits} event found with description '{search_argument}'. Please make it unique such that only 1 event matches.")
        elif hits == 0:
            raise ValueError(f"No event found with description or index '{search_argument}'")
        elif hits == 1:
            return target_index
        
def set_telegramchatid( chat_id):
    return "telegram-chatid={}".format(chat_id)
        
def get_telegramchatid( user):
    entries = user.split(":")
    for entry in entries:
        if "telegram-chatid=" in entry:
            chat_id = entry.split("telegram-chatid=")[1]
            return chat_id