import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .users import Users, UserField
from .constants import ROUTE_USER

class UserAPI:
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

    def create(self, user):
        """
        Create a new user by calling the API.
        """
        user = Users.clean(user)
        url = f"{self.server_url}/{ROUTE_USER}"
        headers = {'Content-Type': 'application/json'}
        response = self.session.post(url, json=user, headers=headers, auth=(self.username, self.password))
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
        headers = {'Content-Type': 'application/json'}
        response = self.session.get(url, params=params, headers=headers, auth=(self.username, self.password))
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
        headers = {'Content-Type': 'application/json'}
        response = self.session.put(url, json=user, headers=headers, auth=(self.username, self.password))
        if response.status_code in range(200, 299):
            return response.json()
        else:
            raise Exception(f"Failed to update user {user_key}. Response code: {response.status_code}, Response: {response.text}")

    def delete(self, user_key):
        """
        Delete a user by calling the API.
        """
        url = f"{self.server_url}/{ROUTE_USER}/{user_key}"
        response = self.session.delete(url, auth=(self.username, self.password))
        if response.status_code not in range(200, 299):
            raise Exception(f"Failed to delete user {user_key}. Response code: {response.status_code}, Response: {response.text}")