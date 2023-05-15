import time
import requests
import sys
import os
from datetime import datetime, timedelta
from events import write_events_to_csv
from requests.exceptions import ConnectionError

def start_client(CSV_PATH, BASE_URL, USERNAME, PASSWORD):
    interval_seconds = 60  # Adjust this value to your desired interval in seconds
    while True:
        try:
            # Deduct some seconds to account for delay of writing file when last retrieved
            last_change = datetime.fromtimestamp(os.path.getmtime(CSV_PATH) - 10).isoformat()
            headers = {'Content-Type': 'application/json'}
            response = requests.get(f"{BASE_URL}/event", params={'last_change': last_change}, headers=headers, auth=(USERNAME, PASSWORD))
            if response.status_code == 200:
                events = response.json()
                write_events_to_csv(CSV_PATH, events)
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
    start_client( CSV_PATH = sys.argv[1], BASE_URL = sys.argv[2], USERNAME = sys.argv[3], PASSWORD = sys.argv[4])