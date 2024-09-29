import imaplib
import email
import re
import time
import sys
import yaml
import html
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from events import Events, EventField, DATE_FORMAT, TIME_FORMAT, RECORD
from events_api import create_event_api
from ics import Calendar
import math  # Define math module
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9

CONTENT_TYPE_PLAIN = "text/plain"
CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_CALENDAR = "text/calendar"

def start_bot(CNFG_PATH, IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):   
    # Load the YAML config file
    with open( CNFG_PATH, 'r') as file:
        config = yaml.safe_load(file)

    # Configure the logging
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

    logging.info( f"Config file {CNFG_PATH} found") 

    # Loop and evaluate every new message based on the configuration
    while True:
        try:
            # Connect to IMAP server
            imap = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)
            resp, caps = imap.capability()
            if b'STARTTLS' in caps[0]:
                imap.starttls()
            imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            imap.select('inbox')

            # search for all unseen emails
            #imap.search(None, 'UNSEEN')

            for msg_id in imap.search(None, 'UNSEEN')[1][0].split():
                status, msg_data = imap.fetch(msg_id, '(RFC822)')

                msg = email.message_from_bytes(msg_data[0][1])
                subject = msg['Subject']

                # process each email type 
                for type in config['emails']:
                    body = {}
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if part.get_content_type() == CONTENT_TYPE_PLAIN:
                            body[CONTENT_TYPE_PLAIN] = part.get_payload(decode=True).decode('utf-8')
                        elif part.get_content_type() == CONTENT_TYPE_HTML:
                            # nescape special HTML codes such as &amp; etc
                            body[CONTENT_TYPE_HTML]  = html.unescape(part.get_payload(decode=True).decode('utf-8'))
                        elif part.get_content_type() == CONTENT_TYPE_CALENDAR:
                            vcalendar = part.get_payload(decode=True).decode('utf-8')
                            # Parse the vCalendar data
                            calendar = Calendar(vcalendar)
                            # Access events in the calendar
                            body[CONTENT_TYPE_CALENDAR] = [event.__dict__ for event in calendar.events]

                    # html can be converted to plain if required
                    if type['content_type'] == CONTENT_TYPE_PLAIN and CONTENT_TYPE_HTML in body:
                        soup = BeautifulSoup(body[CONTENT_TYPE_HTML], 'html.parser')
                        body[CONTENT_TYPE_PLAIN]  = soup.get_text()
                        text = soup.get_text()

                    # process email if content type available
                    events = []
                    if type['content_type'] in body:
                        content = {}
                        content['subject'] = subject
                        content['body'] = body[type['content_type']]
                        # by default email is matched unless a match_regex fails end returns empty value
                        event ={}
                        # default values
                        event['match'] = True 
                        event[EventField.RECORD.value] = RECORD
                        event[EventField.PASSWORD.value] = ""
                        event['datetime'] = ""
                        event['url'] = ""
                        event[EventField.DURATION.value] = ""
                        # process sections
                        calendar_event_id = 0
                        for section in type['sections']:
                            if section['section'] == 'calendar':
                                if calendar_event_id < len(body[CONTENT_TYPE_CALENDAR]):
                                    calendar_event = body[CONTENT_TYPE_CALENDAR][calendar_event_id]
                                    # finish processing current event
                                    if calendar_event_id > 0:
                                        events.append(event)
                                    calendar_event_id += 1
                                else:
                                    # no more calendar events
                                    break

                            for key, value in section.items():
                                if "_" in key:
                                    attribute, category = key.split("_")
                                    if category == "regex":
                                        # retrieve from content via regex
                                        if attribute == 'datetime':
                                            datetime_matches = re.compile(value).findall(content[section['section']])
                                            try:
                                                event[attribute] = [datetime.strptime(dt_str, section['datetime_format']) for dt_str in datetime_matches]
                                            except ValueError as error:
                                                event[attribute] = ''
                                        else:
                                            match = re.compile(value.replace("\\\\", "\\")).search(content[section['section']])
                                            if match:
                                                # group(1) is the first () in regex
                                                event[attribute] = match.group(1)
                                            else:
                                                event[attribute] = ""
                                    elif category == "value":
                                        # value is directly specified
                                        event[attribute] = value
                                    elif category == "attribute":
                                        if section['section'] == 'calendar':
                                            if value == '_begin':
                                                event[attribute] = [calendar_event[value].datetime]  # Set as first item of list
                                            elif value == 'duration':
                                                event[attribute] = math.ceil((calendar_event['_end_time'] - calendar_event['_begin']).total_seconds() / 60)
                                            elif value == '_timezone':
                                                event[attribute] =  next(iter(calendar_event['_classmethod_kwargs']['tz']))
                                            else:
                                                event[attribute] = calendar_event[value]
                                    elif category == "mapping":
                                        mapping_dict = eval(section[attribute+"_mapping"])
                                        if event[attribute] in mapping_dict:
                                            event[attribute] = mapping_dict[event[attribute]]
                                        else:
                                            event[attribute] = ""
                                            logging.warning( f"Mapping {attribute} not found for {event[attribute]}")
                                
                        # add the last event
                        events.append(event)

                        # event should be stored 
                        for event in events:
                            if event['match'] and event['url']:
                                dates = ''
                                for date in event['datetime']:
                                    # if no date was provided, use todays date in events local timezone
                                    if date.year == 1900 and date.month == 1 and date.day == 1:
                                        today_local = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value])).date()
                                        date = date.replace(year=today_local.year, month=today_local.month, day=today_local.day)
                                    # add local timezone of event
                                    date_local = date.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
                                    # list of dates
                                    if dates:
                                        dates = dates + ","
                                    dates = dates + date_local.strftime(DATE_FORMAT)
                                if dates:    
                                    # some data cleansing
                                    event[EventField.DESCRIPTION.value] = event[EventField.DESCRIPTION.value].strip().replace(" ", "_")
                                    event[EventField.WEEKDAY.value] = dates
                                    event[EventField.TIME.value] = date_local.strftime(TIME_FORMAT)
                                    event[EventField.DURATION.value] = event[EventField.DURATION.value]

                                    # if id is not set, use url
                                    if EventField.ID.value not in event and 'url' in event:
                                        event[EventField.ID.value] = event['url']

                                    event = Events.validate( event)
                                    create_event_api(event, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD)
                                    eventStr = f"Event {event[EventField.DESCRIPTION.value]} {event[EventField.WEEKDAY.value]} {event[EventField.TIME.value]} {event[EventField.TIMEZONE.value]}"
                                    logging.info( f"{eventStr} added")

                        # Mark the message as read
                        imap.store(msg_id, '+FLAGS', '\\Seen')
                                
            # Close the IMAP connection
            imap.close()
            imap.logout()

            # Wait for 1 mins before checking again
            time.sleep(1*60)
            
        except Exception as error:
                if isinstance(error, KeyboardInterrupt):
                    # Exit the program if the exception is a KeyboardInterrupt
                    raise error
                else:
                    logging.error( error.args[0])
            
if __name__ == "__main__":
    start_bot( CNFG_PATH = sys.argv[1], IMAP_SERVER = sys.argv[2], IMAP_PORT = sys.argv[3], EMAIL_ADDRESS = sys.argv[4], EMAIL_PASSWORD = sys.argv[5], SERVER_URL = sys.argv[6], SERVER_USERNAME = sys.argv[7], SERVER_PASSWORD = sys.argv[8])