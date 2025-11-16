import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException

from .users import Users, UserField
from .constants import ROUTE_USER, ROUTE_USER_NOTIFY

class UserAPI:
    def __init__(self, server_url, username, password, retries=3, backoff_factor=0.5, status_forcelist=None):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [500, 502, 503, 504]
        self._setup_session()

    def _setup_session(self):
        """Set up the session with retry configuration and basic authentication."""
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({
            "Connection": "keep-alive",
            "Content-Type": "application/json"
        })
        
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
        
    def notify(self, user_key: str, message: str, subject: str = None, additional_emails: list = None) -> dict:
        """
        Send a notification to a user.
        
        Args:
            user_key: The key of the user to notify
            message: The message to send
            subject: Optional subject for the notification
            additional_emails: Optional list of additional email addresses to notify
            
        Returns:
            dict: Response from the server
        """
        data = {
            "user_key": user_key,
            "message": message,
            "subject": subject,
            "additional_emails": additional_emails or []
        }
        
        response = self._make_request(
            "POST",
            f"{self.server_url}{ROUTE_USER_NOTIFY}",
            json=data
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()
        
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
            if last_response is not None:
                return last_response
            raise

    def create(self, user):
        """
        Create a new user by calling the API.
        """
        user = Users.clean(user)
        url = f"{self.server_url}/{ROUTE_USER}"
        headers = {'Content-Type': 'application/json'}
        
        response = self._make_request(
            "POST",
            url,
            json=user,
            headers=headers,
            auth=(self.username, self.password)
        )
        
        if response.status_code in range(200, 299):
            return response.json()
        else:
            raise Exception(f"Failed to create user. Response code: {response.status_code}, Response: {response.text}")

    def get(self, filters=None):
        """
        Retrieve users based on filter parameters.
        Each filter parameter should be an array where the first element is the attribute,
        the second is the operator, and the third is the value.
        """
        url = f"{self.server_url}/{ROUTE_USER}"
        params = {}
        if filters:
            for i, entry in enumerate(filters):
                if len(entry) == 3:
                    attribute, operator, value = entry
                    params[f"Filter.{i + 1}.Name"] = attribute
                    params[f"Filter.{i + 1}.Operator"] = operator
                    params[f"Filter.{i + 1}.Value"] = value
                    
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
            raise Exception(f"Failed to retrieve user(s). Response code: {response.status_code}, Response: {response.text}")

    def update(self, user):
        """
        Update a user by calling the API.
        """
        user = Users.clean(user)
        user_key = user[UserField.KEY.value]
        url = f"{self.server_url}/{ROUTE_USER}/{user_key}"
        
        response = self._make_request(
            "PUT",
            url,
            json=user,
            headers={'Content-Type': 'application/json'},
            auth=(self.username, self.password)
        )
        
        if response.status_code in range(200, 299):
            return response.json()
        else:
            raise Exception(f"Failed to update user {user_key}. Response code: {response.status_code}, Response: {response.text}")

    def delete(self, user_key):
        """
        Delete a user by calling the API.
        """
        url = f"{self.server_url}/{ROUTE_USER}/{user_key}"
        
        response = self._make_request(
            "DELETE",
            url,
            auth=(self.username, self.password)
        )
        
        if response.status_code not in range(200, 299):
            raise Exception(f"Failed to delete user {user_key}. Response code: {response.status_code}, Response: {response.text}")