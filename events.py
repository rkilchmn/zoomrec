import csv
import time
import re
import validators
import subprocess
from datetime import datetime, timedelta

CSV_DELIMITER = ";"

DATE_FORMAT = '%d/%m/%Y'
TIME_FORMAT = '%H:%M'
RECORD = 'true'

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

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
        writer = csv.DictWriter(file, fieldnames=['weekday', 'time', 'duration', 'id', 'password', 'description', 'record'], delimiter=CSV_DELIMITER)
        writer.writeheader()
        for event in events:
            writer.writerow(event)

def validate_event(event):
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
            command = ["curl", "-Ls", "-w", "%{url_effective}", "-o", "/dev/null", event['id']]
            result = subprocess.run(command, capture_output=True, text=True)
            event['id'] = result.stdout.strip()
            
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