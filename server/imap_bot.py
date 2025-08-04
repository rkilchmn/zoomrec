import imaplib
import email
import re
import time
import yaml
import html
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from ics import Calendar
import os
import math  # Define math module
import json
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9
from typing import Optional

from shared.utilities import start_logging, start_debug
from shared.ai_service import LLMChat
from shared.events import Events, EventField, DATETIME_FORMAT, EventStatus
from shared.events_api import EventAPI
from shared.users import UserField, Users
from shared.users_api import UserAPI
from shared.utilities import start_logging, start_debug
from shared import constants
from shared.constants import LOG_IMAP_BOT_FILENAME, DEBUG_MODULE_IMAP_BOT, DATE_FORMAT, TIME_FORMAT
from server.telegram_bot import CMD_ADD_EVENT

def format_event_command(event: dict, user_login: str) -> str:
    """
    Format an event into a command string matching the Telegram bot's format.
    
    Args:
        event: Dictionary containing event data with EventField keys.
               Fields may be empty strings if no valid value is available.
        user_login: Login name of the user associated with the event
        
    Returns:
        str: Formatted command string with all fields, including empty ones
        
    Raises:
        ValueError: If the event dictionary is invalid or missing required keys
    """
    if not event or not isinstance(event, dict):
        raise ValueError("Event must be a non-empty dictionary")
    
    if not user_login or not isinstance(user_login, str):
        raise ValueError("User login must be a non-empty string")
    
    try:
        # Convert all values to strings, using <fieldname> if empty
        def safe_get(field, default=""):
            value = event.get(field.value, default)
            return str(value) if value else f"<{field.value.lower()}>"
            
        # Get datetime or use <timestamp> if invalid
        dt_str = safe_get(EventField.DTSTART)
        try:
            dt = datetime.strptime(dt_str, DATETIME_FORMAT) if dt_str and "<" not in dt_str else None
        except ValueError:
            dt = None
        
        # Build command parts with all fields, using <fieldname> if empty
        cmd_parts = [
            f"/{CMD_ADD_EVENT}",
            f'"{safe_get(EventField.TITLE)}"',
            f'"{user_login.strip()}"',
            dt.strftime(DATE_FORMAT) if dt else "<date>",
            dt.strftime(TIME_FORMAT) if dt else "<time>",
            safe_get(EventField.TIMEZONE),
            safe_get(EventField.DURATION),
        ]
        
        # Add ID/URL and password if the key exists
        url = safe_get(EventField.URL)
        event_id = safe_get(EventField.ID)
        
        if EventField.URL.value in event:
            cmd_parts.append(f'"{url}"' if "<" not in url else f"<{EventField.URL.value.lower()}>")
        elif EventField.ID.value in event:
            cmd_parts.append(event_id if "<" not in event_id else f"<{EventField.ID.value.lower()}>")
            if EventField.PASSWORD.value in event:
                password = safe_get(EventField.PASSWORD)
                cmd_parts.append(password if "<" not in password else f"<{EventField.PASSWORD.value.lower()}>")
        
        # Add instructions if the key exists
        if EventField.INSTRUCTION.value in event:
            instruction = safe_get(EventField.INSTRUCTION)
            cmd_parts.append(f'"{instruction}"' if "<" not in instruction else f"<{EventField.INSTRUCTION.value.lower()}>")
        
        # Join parts, replacing any empty parts with empty strings
        # This ensures the command structure is maintained even with missing data
        return ' '.join(part if part is not None else '' for part in cmd_parts)
        
    except Exception as e:
        logging.error(f"Error formatting event command: {e}")
        raise

start_logging( LOG_IMAP_BOT_FILENAME)
start_debug(DEBUG_MODULE_IMAP_BOT, os.getenv('DEBUG_PORT_SERVER'))

CONTENT_TYPE_PLAIN = "text/plain"
CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_CALENDAR = "text/calendar"

# Get varsh
BASE_PATH = os.getenv('ZOOMREC_HOME')

EMAIL_TYPE_PATH = os.path.join(BASE_PATH, constants.EMAIL_CONFIG_FILE)
IMAP_SERVER = os.getenv('IMAP_SERVER')
IMAP_PORT = os.getenv('IMAP_PORT')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD')

SERVER_URL  = os.getenv('SERVER_URL')
SERVER_USERNAME  = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD  = os.getenv('SERVER_PASSWORD')

def mapping_ai(attribute_name: str, attribute_value: str, ai_config: dict) -> Optional[str]:
    """
    Maps an attribute value using an AI service.

    Args:
    attribute_name (str): The name of the attribute being mapped.
    attribute_value (str): The value of the attribute being mapped.
    ai_config (dict): A dictionary containing the AI service configuration.

    Returns:
    Optional[str]: The mapped attribute value, or None if an error occurs.
    """
    try:         
        # get default value if it exists
        default = ai_config["default"] if "default" in ai_config else None  

        llm = LLMChat(
            model=ai_config["model"],
            api_url=ai_config["api_url"],
            api_key_env=ai_config["api_key_env"]
        )
        prompt = ai_config["prompt_template"].format(input=attribute_value)
        result = llm.ask(prompt)
        if result is not None:
            return result
        else:
            logging.error(f"Error mapping attribute: No response from LLM. Returning 'default' {default}")
            return default
        
    except Exception as e:
        logging.error(f"Error mapping attribute: {attribute_name} value: {attribute_value} using AI. Returning 'default' {default}.\nException: {str(e)}", exc_info=True)
        return default

def run_bot():   
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
                        try:
                            charset = part.get_content_charset() or 'utf-8'
                            if part.get_content_type() == CONTENT_TYPE_PLAIN:
                                body[CONTENT_TYPE_PLAIN] = part.get_payload(decode=True).decode(charset, errors='replace')
                            elif part.get_content_type() == CONTENT_TYPE_HTML:
                                # unescape special HTML codes such as &amp; etc
                                body[CONTENT_TYPE_HTML]  = html.unescape(part.get_payload(decode=True).decode(charset, errors='replace'))
                            elif part.get_content_type() == CONTENT_TYPE_CALENDAR:
                                vcalendar = part.get_payload(decode=True).decode(charset, errors='replace')
                                # Parse the vCalendar data
                                calendar = Calendar(vcalendar)
                                body[CONTENT_TYPE_CALENDAR] = calendar
                        except Exception as e:
                            logging.error(f"Error decoding email {msg_id} - {subject} - {content_type}: {str(e)}")

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
                        event['cancelled'] = False
                        
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
                                            # save previous event
                                            events.append(event)
                                            # init new event
                                            event = {}
                                            event = Events.set_missing_defaults(event)
                                            event['cancelled'] = False
                                        # cancellation
                                        event['cancelled'] = content['body'].method == 'CANCEL'
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
                                            if isinstance(value, str):
                                                event[attribute] = value
                                            else:
                                                event[attribute] = json.dumps(value)
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
                                            mapping_list = section[attribute + "_mapping"]
                                            mapping_dict = {list(d.keys())[0]: list(d.values())[0] for d in mapping_list}
                                            if event[attribute] in mapping_dict:
                                                event[attribute] = mapping_dict[event[attribute]]
                                            else:
                                                event[attribute] = ""
                                                logging.warning(f"Mapping {attribute} not found for value: {event[attribute]}")
                                        elif category == "mapping-ai":
                                            config_dict = section[attribute+"_mapping-ai"]
                                            event[attribute] = mapping_ai(attribute, event[attribute], config_dict)
                                if not section['section'] == 'calendar':
                                    # only one loop if not calendar
                                    break

                        # add the last event
                        events.append(event)

                        # event should be stored 
                        for event in events:
                            if event['match']:
                                # lookup user by login
                                user = None
                                try:
                                    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                                        user = user_api.get(filters=[[UserField.LOGIN.value, '=', type['user_login']]])[0]
                                except Exception as error:
                                    logging.error( f"User {type['user_login']} not found.")
                                    continue
                            
                                event[EventField.USER_KEY.value] = user[UserField.KEY.value]

                                # if no date was provided, use todays date in events local timezone
                                dtstart = event[EventField.DTSTART.value]
                                if dtstart.year == 1900 and dtstart.month == 1 and dtstart.day == 1:
                                    if event[EventField.TIMEZONE.value] is not None:
                                        today_local = datetime.now(ZoneInfo(event[EventField.TIMEZONE.value])).date()
                                        dtstart = dtstart.replace(year=today_local.year, month=today_local.month, day=today_local.day)
                                        # add local timezone of event
                                        dtstart = dtstart.replace(tzinfo=ZoneInfo(event[EventField.TIMEZONE.value]))
                                # convert to date/time string (as events exoects that)
                                event[EventField.DTSTART.value] = dtstart.strftime(DATETIME_FORMAT)

                                eventStr = f"Event {event[EventField.TITLE.value]} {event[EventField.DTSTART.value]} {event[EventField.TIMEZONE.value]}"

                                # validate event
                                try:
                                    event = Events.validate( event)
                                except ValueError as error:
                                    # Format the event as a command string before continuing
                                    try:
                                        logging.error(f"Event '{eventStr}' failed validation: '{error}'")
                                        Users.send_message(user, f"Event '{eventStr}' not valid. {error}")
                                        # format add event command to help user create the event manually
                                        add_event_msg = format_event_command(event, type['user_login'])
                                        Users.send_message(user, f"{add_event_msg}")
                                    except Exception as format_error:
                                        logging.error(f"Error formatting event: {format_error}")
                                        
                                    continue
                            
                                # lookup existing event 
                                with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
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
                                            existing_events = event_api.get(filters=[filter_existing])
                                            if len(existing_events) == 1:
                                                existing_event = existing_events[0]
                                            elif len(existing_events) == 0:
                                                logging.info( f"Existing Event with filter {filter_existing} not found.")
                                            else:
                                                logging.warning( f"Multiple existing Events with filter {filter_existing} found: {len(existing_events)}. Not updating existing events.")
                                        except Exception as error:
                                            logging.error( f"Existing Event with filter {filter_existing} not found. {error}", exc_info=True)

                                    
                                        if existing_event:
                                            if event['cancelled']:
                                                event_api.delete(existing_event[EventField.KEY.value])
                                                logging.info( f"{eventStr} deleted due to cancellation")
                                            else:
                                                event[EventField.KEY.value] = existing_event[EventField.KEY.value]
                                                event_api.update(event)
                                                logging.info( f"{eventStr} updated")
                                        else:
                                            if not event['cancelled']:
                                                event_api.create(event)
                                                logging.info( f"{eventStr} added")
                                            else:
                                                logging.info( f"{eventStr} was cancelled and therefore not added")
            
                        # Mark the message as read
                        imap.store(msg_id, '+FLAGS', '\\Seen')
                            
            # Close the IMAP connection
            imap.close()
            imap.logout()

            # Wait for 1 mins before checking again
            time.sleep(1*60)
        
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                # Exit the program if the exception is a KeyboardInterrupt
                raise e
            else:
                logging.error(f"An error occurred: {e}", exc_info=True)  # Enhanced to include full stack trace
            
if __name__ == "__main__":
    if not (EMAIL_PASSWORD and IMAP_SERVER and IMAP_PORT and EMAIL_ADDRESS and SERVER_URL and SERVER_USERNAME and SERVER_PASSWORD):
        print("IMAP details missing or API server details missing. Starting IMAP email bot failed!")
    else:
        run_bot()