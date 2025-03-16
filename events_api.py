import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from events import EventField, Events  # Adjust the import as necessary

def update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event):
    """
    Update the status of an event by calling the API.
    """
    event = Events.clean(event)
    event_key = event[EventField.KEY.value]
    url = f"{SERVER_URL}/event/{event_key}"
    headers = {'Content-Type': 'application/json'}

    response = requests.put(url, json=event, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in range(200, 299):
        raise Exception(f"Failed to update event {event_key}. Response code: {response.status_code}, Response: {response.text}")

def create_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event):
    """
    Create a new event by calling the API.
    """
    event = Events.clean(event)
    url = f"{SERVER_URL}/event"
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, json=event, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code in range(200, 299):
        return response.json()
    else:
        raise Exception(f"Failed to create event. Response code: {response.status_code}, Response: {response.text}")  

def delete_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event_key):
    """
    Delete an event by calling the API.
    """
    url = f"{SERVER_URL}/event/{event_key}"
    
    response = requests.delete(url, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in range(200, 299):
        raise Exception(f"Failed to delete event {event_key}. Response code: {response.status_code}, Response: {response.text}")

def get_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event_key=None, filters=None):
    """
    Retrieve events based on either an event key or filter parameters.
    Each filter parameter should be an array where the first element is the attribute,
    the second is the operator, and the third is the value.
    """
    url = f"{SERVER_URL}/event"
    params = {}

    # Check for event_key
    if event_key:
        url += f"/{event_key}"
    elif filters:
        for i, entry in enumerate(filters):
            if len(entry) == 3:  # Ensure the query has three elements
                attribute, operator, value = entry
                # Construct the filter-style query
                params[f"Filter.{i + 1}.Name"] = attribute
                params[f"Filter.{i + 1}.Operator"] = operator
                params[f"Filter.{i + 1}.Value"] = value

    headers = {'Content-Type': 'application/json'}
    response = requests.get(url, params=params, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))

    if response.status_code == 200: # success, content returned
        return response.json()
    elif response.status_code == 204: # success, NO content returned
        return []
    else:
        raise Exception(f"Failed to retrieve event(s). Response code: {response.status_code}, Response: {response.text}")

def get_next_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, client_id, event_type = None, lead_time_sec=0, trail_time_sec=0):

    url = f"{SERVER_URL}/event/next"
    params = {
        'client_id': client_id,
        'event_type': event_type,
        'lead_time_sec': lead_time_sec,
        'trail_time_sec': trail_time_sec
    }
    
    headers = {'Content-Type': 'application/json'}
    response = requests.get(url, params=params, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    
    if response.status_code == 200:  # success, content returned
        response_data = response.json()
        # restore datetime  including timezone
        response_data['dtstart_instance'] = datetime.fromisoformat(response_data['dtstart_instance'])
        response_data['dtstart_instance'] = response_data['dtstart_instance'].replace(tzinfo=ZoneInfo(response_data['timezone']))
        response_data['dtend_instance'] = datetime.fromisoformat(response_data['dtend_instance'])
        response_data['dtend_instance'] = response_data['dtend_instance'].replace(tzinfo=ZoneInfo(response_data['timezone']))
        response_data['dtnow'] = datetime.fromisoformat(response_data['dtnow'])
        response_data['dtnow'] = response_data['dtnow'].replace(tzinfo=ZoneInfo(response_data['timezone']))
        return response_data
    elif response.status_code == 204:  # success, NO content returned
        return None
    else:
        raise Exception(f"Failed to retrieve next event. Response code: {response.status_code}, Response: {response.text}")