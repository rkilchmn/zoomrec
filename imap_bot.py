import imaplib
import email
import re
import time
import yaml
import html
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from events import Events, EventField, DATETIME_FORMAT, EventType, EventStatus
from events_api import create_event_api, get_event_api, update_event_api
from users import UserField
from users_api import get_user_api
from ics import Calendar
import os
import math  # Define math module
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9

CONTENT_TYPE_PLAIN = "text/plain"
CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_CALENDAR = "text/calendar"

# Get vars
BASE_PATH = os.getenv('ZOOMREC_HOME')

EMAIL_TYPE_PATH = os.path.join(BASE_PATH, "email_types.yaml")
IMAP_SERVER = os.getenv('IMAP_SERVER')
IMAP_PORT = os.getenv('IMAP_PORT')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD')

SERVER_URL  = os.getenv('SERVER_URL')
SERVER_USERNAME  = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD  = os.getenv('SERVER_PASSWORD')

def start_bot():   
    # Load the YAML config file
    with open( EMAIL_TYPE_PATH, 'r') as file:
        config = yaml.safe_load(file)

    # Configure the logging
    logLevel = getattr(logging, os.getenv( "LOG_LEVEL", "INFO"), logging.INFO)
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logLevel)

    logging.info( f"Config file {EMAIL_TYPE_PATH} found") 

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
                            body[CONTENT_TYPE_CALENDAR] = calendar

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
                        
                        event = {}
                        event = Events.set_missing_defaults(event)
                        event['match'] = True # by default email is matched unless a match_regex fails end returns empty value
                        
                        # process sections
                        first = True
                        eventIter = None
                        for section in type['sections']:
                            # loop for calendar events
                            while True:
                                if section['section'] == 'calendar' and content['body']:
                                    if eventIter is None:
                                        eventIter = iter(content['body'].events)
                                    else:
                                        first = False
                                    try:
                                        calendar_event = next(eventIter)
                                        if not first:
                                            events.append(event)
                                    except StopIteration:
                                        # no more calendar events
                                        break
                            
                                for key, value in section.items():
                                    if "_" in key:
                                        attribute, category = key.split("_")
                                        if category == "regex":
                                            # retrieve from content via regex
                                            if attribute == EventField.DTSTART.value:
                                                datetime_matches = re.compile(value).findall(content[section['section']])
                                                try:
                                                    event[attribute] = datetime.strptime(datetime_matches[0], section['dtstart_format']) if datetime_matches else ''
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
                                                if value == 'begin':
                                                    event[attribute] = calendar_event.begin.datetime
                                                elif value == 'duration':
                                                    event[attribute] = math.ceil((calendar_event.end - calendar_event.begin).total_seconds() / 60)
                                                elif value == 'timezone':
                                                    found = False
                                                    for item in calendar_event.extra:
                                                        if item.name == 'TZID':
                                                            found = True
                                                            event[attribute] = item.value
                                                    if (not found):
                                                        event[attribute] = list(calendar_event._classmethod_kwargs['tz'].keys())[0] 
                                                elif value == 'rrule':
                                                    for item in calendar_event.extra:
                                                        if item.name == 'RRULE':
                                                            event[attribute] = item.value
                                                else:
                                                    event[attribute] = calendar_event.__dict__[value]
                                        elif category == "mapping":
                                            mapping_dict = eval(section[attribute+"_mapping"])
                                            if event[attribute] in mapping_dict:
                                                event[attribute] = mapping_dict[event[attribute]]
                                            else:
                                                event[attribute] = ""
                                                logging.warning( f"Mapping {attribute} not found for {event[attribute]}")

                                if not section['section'] == 'calendar':
                                    # only one loop if not calendar
                                    break

                        # add the last event
                        events.append(event)

                        # event should be stored 
                        for event in events:
                            if event['match']:
                                dtstart = event[EventField.DTSTART.value]
                                # if no date was provided, use todays date in events local timezone
                                if dtstart.year == 1900 and dtstart.month == 1 and dtstart.day == 1:
                                    today_local = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value])).date()
                                    dtstart = dtstart.replace(year=today_local.year, month=today_local.month, day=today_local.day)
                                # add local timezone of event
                                dtstart_local = dtstart.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
                                event[EventField.DTSTART.value] = dtstart_local.strftime(DATETIME_FORMAT)

                                eventStr = f"Event {event[EventField.TITLE.value]} {event[EventField.DTSTART.value]} {event[EventField.TIMEZONE.value]}"
                                try:
                                    # lookup user by login
                                    user = None
                                    try:
                                        user = get_user_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, filters=[[UserField.LOGIN.value, '=', section['user_login']]])[0]
                                    except Exception as error:
                                        logging.error( f"User {section['user_login']} not found.")
                                        continue
                                
                                    event[EventField.USER_KEY.value] = user[UserField.KEY.value]
                                    # validate event
                                    event = Events.validate( event)
                                
                                    # lookup existing event 
                                    filter_existing = None
                                    existing_event = None
                                    if event[EventField.ID.value]:
                                        # Filter to get event by ID
                                        filter_existing = [EventField.ID.value, "=", event[EventField.ID.value]]
                                    elif event[EventField.URL.value]:
                                         # Filter to get event by ID
                                        filter_existing = [EventField.URL.value, "=", event[EventField.URL.value]]
                                    
                                    if filter_existing:
                                        try:    
                                            filter_not_deleted = [EventField.STATUS.value,"!=",EventStatus.DELETED.value]
                                            existing_events = get_event_api( SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, 
                                                                            filters=[filter_existing, filter_not_deleted])
                                            if len(existing_events) == 1:
                                                existing_event = existing_events[0]
                                            elif len(existing_events) == 0:
                                                logging.info( f"Existing Event with filter {filter_existing} not found.")
                                            else:
                                                logging.warning( f"Multiple existing Events with filter {filter_existing} found: {len(existing_events)}. Not updating existing events.")
                                        except Exception as error:
                                            logging.error( f"Existing Event with filter {filter_existing} not found. {error}")

                                    if existing_event:
                                        event[EventField.KEY.value] = existing_event[EventField.KEY.value]
                                        update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
                                        logging.info( f"{eventStr} updated")
                                    else:
                                        create_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
                                        logging.info( f"{eventStr} added")
                                
                                except ValueError as error:
                                    logging.error( f"Validation error {eventStr}. {error.args[0]}")
            
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
                    logging.exception("An error occurred")  # Enhanced to include full stack trace
            
if __name__ == "__main__":
    if not (EMAIL_PASSWORD and IMAP_SERVER and IMAP_PORT and EMAIL_ADDRESS):
        print("IMAP details missing. No IMAP email bot will be started!")
    else:
        start_bot()