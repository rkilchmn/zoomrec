import requests
from users import Users, UserField

def create_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user):
    """
    Create a new user by calling the API.
    """
    user = Users.clean(user)
    url = f"{SERVER_URL}/user"
    headers = {'Content-Type': 'application/json'}
    
    response = requests.post(url, json=user, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code in range(200, 299):
        return response.json()
    else:
        raise Exception(f"Failed to create user. Response code: {response.status_code}, Response: {response.text}")     

def get_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user_key=None, filters=None):
    """
    Retrieve users based on either a user key or filter parameters.
    Each filter parameter should be an array where the first element is the attribute,
    the second is the operator, and the third is the value.
    """
    url = f"{SERVER_URL}/user"
    params = {}

    # Check for user_key
    if user_key:
        url += f"/{user_key}"
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
        raise Exception(f"Failed to retrieve user(s). Response code: {response.status_code}, Response: {response.text}")

def update_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user):
    """
    Update a user by calling the API.
    """
    user = Users.clean(user)
    user_key = user[UserField.KEY.value]
    url = f"{SERVER_URL}/user/{user_key}"
    headers = {'Content-Type': 'application/json'}
    
    response = requests.put(url, json=user, headers=headers, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code in range(200, 299):
        return response.json()
    else:
        raise Exception(f"Failed to update user {user_key}. Response code: {response.status_code}, Response: {response.text}")  

def delete_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user_key):
    """
    Delete a user by calling the API.
    """
    url = f"{SERVER_URL}/user/{user_key}"
    
    response = requests.delete(url, auth=(SERVER_USERNAME, SERVER_PASSWORD))
    if response.status_code not in range(200, 299):
        raise Exception(f"Failed to delete user {user_key}. Response code: {response.status_code}, Response: {response.text}") 