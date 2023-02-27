import csv
import time
import re
import validators
import subprocess
from datetime import datetime

CSV_DELIMITER = ";"

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
         # Validate weekday
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if event['weekday'].lower() not in weekdays:
            try:
                date_obj = datetime.strptime(event['weekday'], "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid weekday or date '{event['weekday']}'. Use only: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday or date in YYYY-MM-DD format.")
    else:
        raise ValueError("Missing attribute weekday.")

    if event['time']:
        # Validate time
        try:
            time.strptime(event['time'], '%H:%M')
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