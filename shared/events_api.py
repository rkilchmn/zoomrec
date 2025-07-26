import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException
import logging

from .events import EventField, Events
from .constants import ROUTE_EVENT, ROUTE_EVENT_NEXT

class EventAPI:
    def __init__(self, server_url, username, password, retries=3, backoff_factor=0.5, status_forcelist=None):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [500, 502, 503, 504]
        self._setup_session()

    def _setup_session(self):
        """Set up the session with retry configuration."""
        self.session = requests.Session()
        self.session.headers.update({"Connection": "keep-alive"})
        
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            raise_on_status=False  # We'll handle status codes ourselves
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()
        
    def _make_request(self, method, url, **kwargs):
        """Make an HTTP request with retries on connection errors and return the last response on failure."""
        last_response = None
        
        @retry(
            stop=stop_after_attempt(self.retries + 1),  # +1 for initial attempt
            wait=wait_exponential(multiplier=self.backoff_factor),
            retry=retry_if_exception_type(
                requests.exceptions.ConnectionError |
                requests.exceptions.Timeout |
                requests.exceptions.SSLError
            ),
            reraise=True  # Re-raise connection/network errors after retries
        )
        def _request():
            return self.session.request(method, url, **kwargs)

        try:
            return _request()
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.SSLError) as e:
            logging.info(f"Request failed after retries: {e}")
            if last_response is not None:
                return last_response
            raise

    def update(self, event):
        """
        Update the status of an event by calling the API.
        """
        event = Events.clean(event)
        event_key = event[EventField.KEY.value]
        url = f"{self.server_url}/{ROUTE_EVENT}/{event_key}"
        
        try:
            response = self._make_request(
                "PUT",
                url,
                json=event,
                headers={'Content-Type': 'application/json'},
                auth=(self.username, self.password)
            )
            
            if response.status_code not in range(200, 299):
                raise Exception(f"Failed to update event {event_key}. Response code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.info(f"Error in update: {e}")
            raise

    def create(self, event):
        """
        Create a new event by calling the API.
        """
        event = Events.clean(event)
        url = f"{self.server_url}/{ROUTE_EVENT}"
        
        try:
            response = self._make_request(
                "POST",
                url,
                json=event,
                headers={'Content-Type': 'application/json'},
                auth=(self.username, self.password)
            )
            
            if response.status_code in range(200, 299):
                return response.json()
            else:
                raise Exception(f"Failed to create event. Response code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.info(f"Error in create: {e}")
            raise

    def delete(self, event_key):
        """
        Delete an event by calling the API.
        """
        url = f"{self.server_url}/{ROUTE_EVENT}/{event_key}"
        
        try:
            response = self._make_request(
                "DELETE",
                url,
                auth=(self.username, self.password)
            )
            
            if response.status_code not in range(200, 299):
                raise Exception(f"Failed to delete event {event_key}. Response code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.info(f"Error in delete: {e}")
            raise

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
                    
        try:
            response = self._make_request(
                "GET",
                url,
                params=params,
                headers={'Content-Type': 'application/json'},
                auth=(self.username, self.password)
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return []
            else:
                raise Exception(f"Failed to retrieve event(s). Response code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.info(f"Error in get: {e}")
            raise

    def get_next(self, client_id, event_type=None, lead_time_sec=0, trail_time_sec=0):
        """
        Retrieve the next event for the specified client.
        
        Args:
            client_id: The client ID to get the next event for
            event_type: Optional event type filter
            lead_time_sec: Optional lead time in seconds
            trail_time_sec: Optional trail time in seconds
            
        Returns:
            The next event as a dictionary, or None if no events are available
        """
        url = f"{self.server_url}/{ROUTE_EVENT}/{ROUTE_EVENT_NEXT}"
        params = {
            'client_id': client_id,
            'event_type': event_type,
            'lead_time_sec': lead_time_sec,
            'trail_time_sec': trail_time_sec
        }
        
        try:
            response = self._make_request(
                "GET",
                url,
                params=params,
                headers={'Content-Type': 'application/json'},
                auth=(self.username, self.password)
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return None
            else:
                raise Exception(f"Failed to retrieve next event. Response code: {response.status_code}, Response: {response.text}")
        except Exception as e:
            logging.info(f"Error in get_next: {e}")
            raise