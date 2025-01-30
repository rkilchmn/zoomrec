from events_api import create_event_api, update_event_api, get_event_api, delete_event_api
from events import EventField
from users_api import create_user_api, get_user_api, update_user_api, delete_user_api
from users import UserField

# Configuration
SERVER_URL = "http://localhost:8081"
SERVER_USERNAME = "myuser"
SERVER_PASSWORD = "mypassword"

def main():
    # Create a new user
    new_user = {
        UserField.NAME.value : "Roger Test",
        UserField.LOGIN.value: "roger_test",
        UserField.PASSWORD.value: "securepassword",
        UserField.EMAIL.value: "john@doe.net",
    }

    print("Creating user...")
    created_user = create_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, new_user)
    print("User created:", created_user)

    # Retrieve the user
    user_key = created_user[UserField.KEY.value]
    print(f"Retrieving user with key: {user_key}...")
    user = get_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user_key)[0]
    print("User retrieved:", user)

    # Retrieve the user
    user_key = created_user[UserField.KEY.value]
    print(f"Retrieving user with {UserField.LOGIN.value}: {created_user[UserField.LOGIN.value]}...")
    user = get_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, filters=[[[UserField.LOGIN.value,"=",created_user[UserField.LOGIN.value]]]])[0]
    print("User retrieved:", user)

    # Update the user
    print("Updating user...")
    user[UserField.NAME.value] = "Johnathan Doe"
    updated_user = update_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user)
    if updated_user[UserField.NAME.value] != user[UserField.NAME.value]:
        raise Exception("User name not updated")
    print("User updated:", updated_user)

    # # Delete the user
    # print(f"Deleting user with key: {user_key}...")
    # delete_user_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, user_key)
    # print("User deleted.")

    # Define a new event
    new_event = {
        EventField.TYPE.value: "1",
        EventField.TITLE.value: "Test Event",
        EventField.DTSTART.value: "18/09/2025 21:45",
        EventField.TIMEZONE.value: "Australia/Sydney",
        EventField.DURATION.value: "30",
        EventField.RRULE.value: "FREQ=DAILY;COUNT=2",
        EventField.ID.value: "85703777235",
        EventField.PASSWORD.value: "password123",
        EventField.URL.value: "https://us05web.zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1",
        EventField.INSTRUCTION.value: "record=true",
        EventField.USER_KEY.value: updated_user[UserField.KEY.value]
    }

    # Create the event
    print("Creating event...")
    new_event = create_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, new_event)
    print("Event created.")

    # Retrieve the event key (assuming the event key is returned in the response)
    event_key = new_event[EventField.KEY.value]

    # Retrieve the event by key
    print(f"Retrieving event with key: {event_key}...")
    event = get_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event_key)[0]
    print("Event retrieved:", event)

     # Retrieve the event by user
    print(f"Retrieving event with {EventField.USER_KEY.value}: {updated_user[UserField.KEY.value]}...")
    event = get_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, filters=[[EventField.USER_KEY.value, "=", updated_user[UserField.KEY.value]]])[0]
    print("Event retrieved:", event)

    # Modify the event
    print("Modifying event...")
    event[EventField.TITLE.value] = "Updated Test Event"
    update_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event)
    print("Event modified.")

    # Retrieve the modified event
    print(f"Retrieving modified event with key: {event_key}...")
    modified_event = get_event_api(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD, event_key)[0]
    print("Modified event retrieved:", modified_event)
    if modified_event[EventField.TITLE.value] != "Updated Test Event":
        raise Exception("Event title not updated")

    # Delete the event
    # print(f"Deleting event with key: {event_key}...")
    # delete_event_api(event_key, SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD)
    # print("Event deleted.")

if __name__ == "__main__":
    main() 