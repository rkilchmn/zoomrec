import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from datetime import datetime
from .events import EventField, Events
from .constants import ROUTE_EVENT, ROUTE_EVENT_NEXT
class EventAPI:
    def __init__(self, server_url, username, password, retries=3, backoff_factor=0.5, status_forcelist=None):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"Connection": "keep-alive"})
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or [500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def update(self, event):
        """
        Update the status of an event by calling the API.
        """
        event = Events.clean(event)
        event_key = event[EventField.KEY.value]
        url = f"{self.server_url}/{ROUTE_EVENT}/{event_key}"
        headers = {'Content-Type': 'application/json'}
        try:
            response = self.session.put(url, json=event, headers=headers, auth=(self.username, self.password))
            if response.status_code not in range(200, 299):
                raise Exception(f"Failed to update event {event_key}. Response code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.info(f"Connection error in update: {e}")

    def create(self, event):
        """
        Create a new event by calling the API.
        """
        event = Events.clean(event)
        url = f"{self.server_url}/{ROUTE_EVENT}"
        headers = {'Content-Type': 'application/json'}
        try:
            response = self.session.post(url, json=event, headers=headers, auth=(self.username, self.password))
            if response.status_code in range(200, 299):
                return response.json()
            else:
                raise Exception(f"Failed to create event. Response code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.info(f"Connection error in create: {e}")

    def delete(self, event_key):
        """
        Delete an event by calling the API.
        """
        url = f"{self.server_url}/{ROUTE_EVENT}/{event_key}"
        try:
            response = self.session.delete(url, auth=(self.username, self.password))
            if response.status_code not in range(200, 299):
                raise Exception(f"Failed to delete event {event_key}. Response code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.info(f"Connection error in delete: {e}")

    def get(self, filters=None):
        """
        Retrieve events based on filter parameters.
        Each filter parameter should be an array where the first element is the attribute,
        the second is the operator, and the third is the value.
        To retrieve an event by its key, use filters=[[EventField.KEY.value, "=", key_value]]
        """
        url = f"{self.server_url}/{ROUTE_EVENT}"
        params = {}
        if filters:
            for i, entry in enumerate(filters):
                if len(entry) == 3:
                    attribute, operator, value = entry
                    params[f"Filter.{i + 1}.Name"] = attribute
                    params[f"Filter.{i + 1}.Operator"] = operator
                    params[f"Filter.{i + 1}.Value"] = value
        headers = {'Content-Type': 'application/json'}
        try:
            response = self.session.get(url, params=params, headers=headers, auth=(self.username, self.password))
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return []
            else:
                raise Exception(f"Failed to retrieve event(s). Response code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.info(f"Connection error in get: {e}")

    def get_next(self, client_id, event_type=None, lead_time_sec=0, trail_time_sec=0):
        url = f"{self.server_url}/{ROUTE_EVENT}/{ROUTE_EVENT_NEXT}"
        params = {
            'client_id': client_id,
            'event_type': event_type,
            'lead_time_sec': lead_time_sec,
            'trail_time_sec': trail_time_sec
        }
        headers = {'Content-Type': 'application/json'}
        try:
            response = self.session.get(url, params=params, headers=headers, auth=(self.username, self.password))
            if response.status_code == 200:
                response_data = response.json()
                # restore datetime including timezone
                response_data['dtstart_instance'] = datetime.fromisoformat(response_data['dtstart_instance'])
                response_data['dtstart_instance'] = Events.replaceTimezone(response_data['dtstart_instance'], response_data['timezone'])
                response_data['dtend_instance'] = datetime.fromisoformat(response_data['dtend_instance'])
                response_data['dtend_instance'] = Events.replaceTimezone(response_data['dtend_instance'], response_data['timezone'])
                response_data['dtstart_instance_lead'] = datetime.fromisoformat(response_data['dtstart_instance_lead'])
                response_data['dtstart_instance_lead'] = Events.replaceTimezone(response_data['dtstart_instance_lead'], response_data['timezone'])
                response_data['dtend_instance_trail'] = datetime.fromisoformat(response_data['dtend_instance_trail'])
                response_data['dtend_instance_trail'] = Events.replaceTimezone(response_data['dtend_instance_trail'], response_data['timezone'])
                response_data['dtnow'] = datetime.fromisoformat(response_data['dtnow'])
                response_data['dtnow'] = Events.replaceTimezone(response_data['dtnow'], response_data['timezone'])
                return response_data
            elif response.status_code == 204:
                return None
            else:
                raise Exception(f"Failed to retrieve next event. Response code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.info(f"Connection error in get_next: {e}")