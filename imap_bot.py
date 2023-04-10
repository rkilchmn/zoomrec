import imaplib
import email
import re
import time
import sys
import yaml
from datetime import datetime

from events import read_events_from_csv, write_events_to_csv, validate_event, DATE_FORMAT, TIME_FORMAT, RECORD
try:
    from zoneinfo import ZoneInfo # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo # < 3.9

def start_bot(CSV_PATH, CNFG_PATH, IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD):   
    # Loop and evaluate every new message based on the subject keyword
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

            # Load the YAML config file
            with open( CNFG_PATH, 'r') as file:
                config = yaml.safe_load(file)

            for msg_id in imap.search(None, 'UNSEEN')[1][0].split():
                status, msg_data = imap.fetch(msg_id, '(RFC822)')

                msg = email.message_from_bytes(msg_data[0][1])
                subject = msg['Subject']
                # Extract class information from the email body
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8')
                        # process each email type
                        for type in config['emails']:
                            content = {}
                            content['subject'] = subject
                            content['body'] = body
                            # by default email is matched unless a match_regex fails end returns empty valu
                            content['match'] = True 
                            content['record'] = RECORD
                            content['password'] = ""
                            content['datetime'] = ""
                            content['url'] = ""
                            content['duration'] = ""
                            # process sections
                            for section in type['sections']:
                                 for key, value in section.items():
                                    if "_" in key:
                                        attribute, category = key.split("_")
                                        if category == "regex":
                                            # retrieve from content via regex
                                            if attribute == 'datetime':
                                                datetime_matches = re.compile(value).findall(content[section['section']])
                                                content[attribute] = [datetime.strptime(dt_str, section['datetime_format']) for dt_str in datetime_matches]
                                            else:
                                                match = re.compile(value.replace("\\\\", "\\")).search(content[section['section']])
                                                if match:
                                                    # group(1) is the first () in regex
                                                    content[attribute] = match.group(1)
                                                else:
                                                    content[attribute] = ""
                                                if attribute+"_mapping" in section and attribute in content:
                                                    mapping_dict = eval(section[attribute+"_mapping"])
                                                    content[attribute] = mapping_dict[content[attribute]]
                                                    
                                        elif category == "value":
                                            # value is directly specified
                                            content[attribute] = value

                            # event should be stored 
                            if content['match'] and content['url']:
                                dates = ''
                                for date in content['datetime']:
                                    # add local timezone of event
                                    date_local = date.replace(tzinfo=ZoneInfo(content['timezone']))
                                    # convert to system timezone
                                    date_system = date_local.astimezone(datetime.now().astimezone().tzinfo)
                                    # list of dates
                                    if dates:
                                        dates = dates + ","
                                    dates = dates + date_system.strftime(DATE_FORMAT)
                                if dates:    
                                    event = {'description': content['description'] ,
                                            'weekday': dates,
                                            'time': date_system.strftime(TIME_FORMAT), 
                                            'duration': content['duration'], 
                                            'id': content['url'], 
                                            'password': content['password'],
                                            'record': RECORD}
                                    try:
                                        event = validate_event( event)
                                    except ValueError as error:
                                        print( error.args[0])

                                    events = read_events_from_csv(CSV_PATH)
                                    events.append(event)
                                    write_events_to_csv(CSV_PATH, events)

                        # Mark the message as read
                        imap.store(msg_id, '+FLAGS', '\\Seen')
                                
            # Close the IMAP connection
            imap.close()
            imap.logout()   

            # Wait for 5 mins before checking again
            time.sleep(5*60)
            
        except Exception as e:
            # if isinstance(e, KeyboardInterrupt) or isinstance(e, yaml.scan): 
                # Exit the program if the exception is a KeyboardInterrupt
            raise e
            
if __name__ == "__main__":
    start_bot( CSV_PATH = sys.argv[1], CNFG_PATH = sys.argv[2], IMAP_SERVER = sys.argv[3], IMAP_PORT = sys.argv[4], EMAIL_ADDRESS = sys.argv[5], EMAIL_PASSWORD = sys.argv[6])