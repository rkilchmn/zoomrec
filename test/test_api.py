from events_api import EventAPI
from events import EventField, EventType, Events
from users_api import UserAPI
from users import UserField, Users

# Configuration
SERVER_URL = "http://localhost:8081"
SERVER_USERNAME = "myuser"
SERVER_PASSWORD = "mypassword"
CLIENT_ID = "550e8400-e29b-41d4-a716-446655440000"

def main():
    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
        # Create a new user
        new_user = {
            UserField.NAME.value : "John Doe",
            UserField.LOGIN.value: "johndoe",
            UserField.PASSWORD.value: "securepassword",
            UserField.EMAIL.value: "john@doe.net",
        }    
        created_user = user = updated_user = None

        # Create user
        try:
            created_user = user_api.create(new_user)
            print(f"Created {Users.nameStr(created_user)}")
        except Exception as e:
            print(f"Failed to create user. Exception: {str(e)}")
            return

        # Retrieve the user
        try:
            user_key = created_user[UserField.KEY.value]
            print(f"Retrieving user with {UserField.LOGIN.value}: {created_user[UserField.LOGIN.value]}...")
            user = user_api.get(filters=[[UserField.LOGIN.value,"=",created_user[UserField.LOGIN.value]]])[0]
            print(f"Retrieved {Users.nameStr(user)}:")
            print(user)
        except Exception as e:
            print(f"Failed to retrieve user. Exception: {str(e)}")
            return

        # Update the user
        try:
            print("Updating user...")
            user[UserField.NAME.value] = "Johnathan Doe"
            user[UserField.PASSWORD.value] = "securepassword2"
            user_api.update(user)
            print(f"Updated {Users.nameStr(user)}")
        except Exception as e:
            print(f"Failed to update user. Exception: {str(e)}")
            return

        # Retrieve the updated user
        try:
            print(f"Retrieving user with key: {user_key}...")
            updated_user = user_api.get(filters=[[UserField.KEY.value, "=", user_key]])[0]
            print(f"Retrieved {Users.nameStr(updated_user)}:")
            print(updated_user)
            if updated_user[UserField.NAME.value] != user[UserField.NAME.value]:
                raise Exception("User update not successful")
        except Exception as e:
            print(f"Failed to retrieve updated user. Exception: {str(e)}")
            return

    # updated_user is now always available for event tests

    # Define a new event
    new_event = {
        EventField.TYPE.value: "1",
        EventField.TITLE.value: "Recuring Test Event Sydney",
        EventField.DTSTART.value: "15/05/2025 11:00",
        EventField.TIMEZONE.value: "Australia/Sydney",
        EventField.DURATION.value: "30",
        EventField.RRULE.value: "FREQ=DAILY;COUNT=2",
        EventField.ID.value: "85703777235",
        EventField.PASSWORD.value: "passcode123",
        EventField.URL.value: "",
        EventField.INSTRUCTION.value: "record=true",
        EventField.USER_KEY.value: updated_user[UserField.KEY.value]
    }

    # Create the events
    print("Creating event 1...")
    with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
        try:
            
                # Create the event
                new_event = event_api.create(new_event)
                print(f"Created {Events.nameStr(new_event)}")

                # Retrieve the event key (assuming the event key is returned in the response)
                event_key = new_event[EventField.KEY.value]
                print(f"Retrieving event with key: {event_key}...")
                event = event_api.get(filters=[[EventField.KEY.value, "=", event_key]])[0]
                print(f"Retrieved {Events.nameStr(event)}:")
                print(event)
                print(f"Retrieved {Events.nameStr(event)}")
                print(event)

                # Modify the event
                print("Modifying event...")
                event[EventField.TITLE.value] = "Updated Recuring Test Event Sydney"
                event_api.update(event)
                print(f"Updated {Events.nameStr(event)}")

                # Retrieve the modified event
                print(f"Retrieving modified event with key: {event_key}...")
                updated_event = event_api.get(filters=[[EventField.KEY.value, "=", event_key]])[0]
                print(f"Retrieved {Events.nameStr(updated_event)}:")
                print(updated_event)
                if updated_event[EventField.TITLE.value] != event[EventField.TITLE.value]:
                    raise Exception("Event update not successfull")
        except Exception as e:
            print(f"EventAPI operation failed. Exception: {str(e)}")

        
        # Define a new event
        new_event2 = {
            EventField.TYPE.value: "1",
            EventField.TITLE.value: "Recuring Test Event New York",
            EventField.DTSTART.value: "16/05/2025 22:00",
            EventField.TIMEZONE.value: "America/New_York",
            EventField.DURATION.value: "45",
            EventField.RRULE.value: "FREQ=DAILY;COUNT=2",
            EventField.ID.value: "",
            EventField.PASSWORD.value: "",
            EventField.URL.value: "https://zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1",
            EventField.INSTRUCTION.value: "record=true",
            EventField.USER_KEY.value: updated_user[UserField.KEY.value]
        }

        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                # Create the event
                print("Creating event 2...")
                new_event2 = event_api.create(new_event2)
                print(f"Created {Events.nameStr(new_event2)}")

                # Retrieve the event key (assuming the event key is returned in the response)
                event_key2 = new_event2[EventField.KEY.value]
                print(f"Retrieving event with key: {event_key2}...")
                event2 = event_api.get(filters=[[EventField.KEY.value, "=", event_key2]])[0]
                print(f"Retrieved {Events.nameStr(event2)}:")
                print(event2)

                # get next event
                print("Getting next event...")
                next_event = event_api.get_next(CLIENT_ID, EventType.ZOOM.value, 60, 300)
                print(f"Next event retrieved: {Events.nameStr(next_event)}")
                print(next_event)
        except Exception as e:
            print(f"EventAPI operation failed. Exception: {str(e)}")

        # Delete the event
        print(f"Deleting event with key: {updated_event[EventField.KEY.value]}...")
        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                event_api.delete(updated_event[EventField.KEY.value])
                print(f"Deleted {Events.nameStr(updated_event)}.")
        except Exception as e:
            print(f"Failed to delete event. Exception: {str(e)}")
    
        # Delete the event
        print(f"Deleting event with key: {event2[EventField.KEY.value]}...")
        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                event_api.delete(event2[EventField.KEY.value])
                print(f"Deleted {Events.nameStr(event2)}.")
        except Exception as e:
            print(f"Failed to delete event. Exception: {str(e)}")

    # Delete the user
    print(f"Deleting user with key: {updated_user[UserField.KEY.value]}...")
    try:
        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            user_api.delete(updated_user[UserField.KEY.value])
            print(f"Deleted {Users.nameStr(updated_user)}.")
    except Exception as e:
        print(f"Failed to delete user. Exception: {str(e)}")

if __name__ == "__main__":
    main() 