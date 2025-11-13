import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .access import Access, AccessField, AccessType
from .constants import ROUTE_ACCESS

# Re-export EXPIRE_AFTER_SECONDS from Access class for convenience
EXPIRE_AFTER_SECONDS = Access.EXPIRE_AFTER_SECONDS

class AccessAPI:
    def __init__(self, server_url, username=None, password=None, retries=3, backoff_factor=0.5, status_forcelist=None):
        self.server_url = server_url
        self.username = username
        self.password = password
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [500, 502, 503, 504]
        self._setup_session()

    def _setup_session(self):
        self.session = requests.Session()
        self.session.headers.update({"Connection": "keep-alive"})
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def _make_request(self, method, url, **kwargs):
        last_response = None

        @retry(
            stop=stop_after_attempt(self.retries + 1),
            wait=wait_exponential(multiplier=self.backoff_factor),
            retry=retry_if_exception_type(
                requests.exceptions.ConnectionError |
                requests.exceptions.Timeout |
                requests.exceptions.SSLError
            ),
            reraise=True
        )
        def _request():
            return self.session.request(method, url, **kwargs)

        try:
            return _request()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.SSLError):
            if last_response is not None:
                return last_response
            raise

    def create(self, access):
        access = Access.clean(access)
        url = f"{self.server_url}/{ROUTE_ACCESS}"
        headers = {'Content-Type': 'application/json'}
        response = self._make_request(
            "POST",
            url,
            json=access,
            headers=headers,
            auth=(self.username, self.password) if self.username and self.password else None
        )
        if response.status_code in range(200, 299):
            return response.json()
        else:
            raise Exception(f"Failed to create access. Response code: {response.status_code}, Response: {response.text}")

    def get(self, filters=None):
        url = f"{self.server_url}/{ROUTE_ACCESS}"
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
            auth=(self.username, self.password) if self.username and self.password else None
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 204:
            return []
        else:
            raise Exception(f"Failed to retrieve access records. Response code: {response.status_code}, Response: {response.text}")

    def update(self, access):
        access = Access.clean(access)
        if AccessField.RESOURCE.value not in access or AccessField.ACCESS_KEY.value not in access:
            raise ValueError("Both resource and access_key are required for update")
            
        url = f"{self.server_url}/{ROUTE_ACCESS}"
        response = self._make_request(
            "PUT",
            url,
            json=access,
            headers={'Content-Type': 'application/json'},
            auth=(self.username, self.password) if self.username and self.password else None
        )
        if response.status_code in range(200, 299):
            return response.json()
        else:
            raise Exception(f"Failed to update access. Response code: {response.status_code}, Response: {response.text}")

    def delete(self, resource, access_key):
        url = f"{self.server_url}/{ROUTE_ACCESS}"
        params = {
            'resource': resource,
            'access_key': access_key
        }
        response = self._make_request(
            "DELETE",
            url,
            params=params,
            auth=(self.username, self.password) if self.username and self.password else None
        )
        if response.status_code not in range(200, 299):
            raise Exception(f"Failed to delete access. Response code: {response.status_code}, Response: {response.text}")

    def validate(self, resource, access_key, access_type):
        """
        Validate if the given resource and access_key combination is valid for the specified access type.
        
        Args:
            resource: The resource to validate access for (must not be None)
            access_key: The access key to validate (must not be None)
            access_type: The type of access to validate (e.g., AccessType.HTTP_SERVER_ACCESS.value, must not be None)
            
        Returns:
            dict: The access record if valid, None otherwise
            
        Raises:
            ValueError: If any required parameter is None
        """
        if resource is None:
            raise ValueError("resource parameter is required and cannot be None")
        if access_key is None:
            raise ValueError("access_key parameter is required and cannot be None")
        if access_type is None:
            raise ValueError("access_type parameter is required and cannot be None")
            
        params = {
            'resource': resource,
            'access_key': access_key,
            'access_type': access_type
        }
            
        response = self._make_request('GET', f"{self.server_url}/{ROUTE_ACCESS}/validate", params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            raise Exception(f"Failed to validate access. Response code: {response.status_code}, Response: {response.text}")
