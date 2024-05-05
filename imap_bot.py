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
from events import read_events_from_csv, write_events_to_csv, validate_event, remove_past_events, get_telegramchatid, DATE_FORMAT, TIME_FORMAT, RECORD
from telegram_bot import send_telegram_message
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9

CONTENT_TYPE_PLAIN = "text/plain"
CONTENT_TYPE_HTML = "text/html"

def start_bot(CSV_PATH, CNFG_PATH, IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD, TELEGRAM_BOT_TOKEN):   
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
                        if part.get_content_type() == CONTENT_TYPE_PLAIN:
                            body[CONTENT_TYPE_PLAIN] = part.get_payload(decode=True).decode('utf-8')
                        elif part.get_content_type() == CONTENT_TYPE_HTML:
                            # nescape special HTML codes such as &amp; etc
                            body[CONTENT_TYPE_HTML]  = html.unescape(part.get_payload(decode=True).decode('utf-8'))
                    # html can be converted to plain if required
                    if type['content_type'] == CONTENT_TYPE_PLAIN and CONTENT_TYPE_HTML in body:
                        soup = BeautifulSoup(body[CONTENT_TYPE_HTML], 'html.parser')
                        body[CONTENT_TYPE_PLAIN]  = soup.get_text()
                        text = soup.get_text()

                    # process email if content type available
                    if type['content_type'] in body:
                        content = {}
                        content['subject'] = subject
                        content['body'] = body[type['content_type']]
                        # by default email is matched unless a match_regex fails end returns empty valu
                        content['match'] = True 
                        content[EventField.RECORD.value] = RECORD
                        content[EventField.PASSWORD.value] = ""
                        content['datetime'] = ""
                        content['url'] = ""
                        content[EventField.DURATION.value] = ""
                        # process sections
                        for section in type['sections']:
                            for key, value in section.items():
                                if "_" in key:
                                    attribute, category = key.split("_")
                                    if category == "regex":
                                        # retrieve from content via regex
                                        if attribute == 'datetime':
                                            datetime_matches = re.compile(value).findall(content[section['section']])
                                            try:
                                                content[attribute] = [datetime.strptime(dt_str, section['datetime_format']) for dt_str in datetime_matches]
                                            except ValueError as error:
                                                content[attribute] = ''
                                        else:
                                            match = re.compile(value.replace("\\\\", "\\")).search(content[section['section']])
                                            if match:
                                                # group(1) is the first () in regex
                                                content[attribute] = match.group(1)
                                            else:
                                                content[attribute] = ""
                                            if attribute+"_mapping" in section and attribute in content and content[attribute]:
                                                mapping_dict = eval(section[attribute+"_mapping"])
                                                if content[attribute] in mapping_dict:
                                                    content[attribute] = mapping_dict[content[attribute]]
                                                else:
                                                    content[attribute] = ""
                                                
                                    elif category == "value":
                                        # value is directly specified
                                        content[attribute] = value

                        # event should be stored 
                        if content['match'] and content['url']:
                            dates = ''
                            for date in content['datetime']:
                                # if no date was provided, use todays date in events local timezone
                                if date.year == 1900 and date.month == 1 and date.day == 1:
                                    today_local = datetime.now(ZoneInfo(content[EventField.TIMEZONE.value])).date()
                                    date = date.replace(year=today_local.year, month=today_local.month, day=today_local.day)
                                # add local timezone of event
                                date_local = date.replace(tzinfo=ZoneInfo(content[EventField.TIMEZONE.value]))
                                # list of dates
                                if dates:
                                    dates = dates + ","
                                dates = dates + date_local.strftime(DATE_FORMAT)
                            if dates:    
                                event = {EventField.DESCRIPTION.value: content[EventField.DESCRIPTION.value].strip().replace(" ", "_"),
                                        EventField.WEEKDAY.value: dates,
                                        EventField.TIME.value: date_local.strftime(TIME_FORMAT), 
                                        EventField.DURATION.value: content[EventField.DURATION.value], 
                                        EventField.ID.value: content['url'], 
                                        EventField.PASSWORD.value: content[EventField.PASSWORD.value],
                                        EventField.RECORD.value: RECORD,
                                        EventField.TIMEZONE.value: content[EventField.TIMEZONE.value],
                                        EventField.USER.value : type[EventField.USER.value]
                                }

                                event = validate_event( event)
                                events = read_events_from_csv(CSV_PATH)
                                events = remove_past_events( events, 300)
                                events.append(event)
                                write_events_to_csv(CSV_PATH, events)
                                eventStr = f"Event {event[EventField.DESCRIPTION.value]} {event[EventField.WEEKDAY.value]} {event[EventField.TIME.value]} {event[EventField.TIMEZONE.value]}"
                                logging.info( f"{eventStr} added")
                                # try to send telegramm message
                                chat_id = get_telegramchatid(event[EventField.USER.value])
                                if chat_id:
                                    if send_telegram_message( TELEGRAM_BOT_TOKEN, chat_id, f"Email bot has added {eventStr}."):
                                        logging.info( "Telegram message successfully sent.")
                                    else:
                                        logging.error( "Error sending Telegram message.")

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
    start_bot( sys.argv[1], CNFG_PATH = sys.argv[2], IMAP_SERVER = sys.argv[3], IMAP_PORT = sys.argv[4], EMAIL_ADDRESS = sys.argv[5], EMAIL_PASSWORD = sys.argv[6], TELEGRAM_BOT_TOKEN = sys.argv[7])