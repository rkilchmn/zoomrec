import requests
from events import EventField, Events  # Adjust the import as necessary

def update_event_api(event, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):
    """
    Update the status of an event by calling the API.
    """
    event = Events.clean_event(event)
    event_key = event[EventField.KEY.value]
    url = f"{SERVER_URL}/event/{event_key}"
    headers = {'Content-Type': 'application/json'}

    response = requests.put(url, json=event, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in [200, 299]:
        raise Exception(f"Failed to update event {event_key}. Response code: {response.status_code}, Response: {response.text}")

def create_event_api(event, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):
    """
    Create a new event by calling the API.
    """
    event = Events.clean_event(event)
    url = f"{SERVER_URL}/event"
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, json=event, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in [200, 299]:
        raise Exception(f"Failed to create event. Response code: {response.status_code}, Response: {response.text}")

def delete_event_api(event_key, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):
    """
    Delete an event by calling the API.
    """
    url = f"{SERVER_URL}/event/{event_key}"
    
    response = requests.delete(url, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in [200, 299]:
        raise Exception(f"Failed to delete event {event_key}. Response code: {response.status_code}, Response: {response.text}")

def get_events_api(last_checked_time, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):
            
    if last_checked_time:
        last_checked_time = last_checked_time.isoformat()
        params = {'last_change': last_checked_time}
    else:
        params = {}

    response = requests.get(f"{SERVER_URL}/event", params, headers = {'Content-Type': 'application/json'}, 
                            auth=(SERVER_USERNAME, SERVER_PASSWORD))
    
    if response.status_code in [200, 299]:
        return response.json()
    else:
        raise Exception(f"Failed to retrieve events. Response code: {response.status_code}, Response: {response.text}")
    
def get_event_api(event_key, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD):
    url = f"{SERVER_URL}/event/{event_key}"
    headers = {'Content-Type': 'application/json'}
    
    response = requests.get(url, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code in [200, 299]:
        return response.json()
    else:
        raise Exception(f"Failed to retrieve event {event_key}. Response code: {response.status_code}, Response: {response.text}")