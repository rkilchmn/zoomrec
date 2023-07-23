import time
import requests
import sys
import os
from datetime import datetime, timedelta
from events import write_events_to_csv
from requests.exceptions import ConnectionError
import base64

def start_client(CSV_PATH, SERVER_URL, USERNAME, PASSWORD):
    interval_seconds = 60  # Adjust this value to your desired interval in seconds
    while True:
        try:
            
            if os.path.exists(CSV_PATH):
                last_change = datetime.fromtimestamp(os.path.getmtime(CSV_PATH)).isoformat()
                params = {'last_change': last_change}
            else:
                params = {}
            response = requests.get(f"{SERVER_URL}/event", params, headers = {'Content-Type': 'application/json'}, 
                                    auth=(USERNAME, PASSWORD))
            if response.status_code == 200:
                events = response.json()
                if events:  # Check if events is not empty
                    write_events_to_csv(CSV_PATH, events)
                    print("Events saved successfully.")
                else:
                    print("No events to save.")
            else:
                print("Error: Failed to retrieve events.")
            time.sleep(interval_seconds)
        except Exception as error:
            if isinstance(error, KeyboardInterrupt):
                # Exit the program if the exception is a KeyboardInterrupt
                raise error
            else:
                print( error.args[0], flush=True)

if __name__ == "__main__":
    start_client( CSV_PATH = sys.argv[1], SERVER_URL = sys.argv[2], USERNAME = sys.argv[3], PASSWORD = sys.argv[4])