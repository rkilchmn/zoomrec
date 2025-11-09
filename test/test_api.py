from shared.events_api import EventAPI
from shared.events import EventField, EventType, Events
from shared.users_api import UserAPI
from shared.users import UserField, Users
from shared.access_api import AccessAPI, EXPIRE_AFTER_SECONDS
from shared.access import AccessField, AccessType
from datetime import datetime, timedelta, timezone
import time

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
            UserField.TIMEZONE.value: "America/New_York",
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
        EventField.DTSTART.value: "15/07/2025 11:00",
        EventField.TIMEZONE.value: "Australia/Sydney",
        EventField.DURATION.value: "30",
        EventField.RRULE.value: "FREQ=DAILY;COUNT=2",
        EventField.ID.value: "85703777235",
        EventField.PASSWORD.value: "passcode123",
        EventField.URL.value: "",
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

        # Test Access API now that we have users and events
        # test_access_api()

        
        # Define a new event
        new_event2 = {
            EventField.TYPE.value: "1",
            EventField.TITLE.value: "Recuring Test Event New York",
            EventField.DTSTART.value: "16/07/2025 22:00",
            EventField.TIMEZONE.value: "America/New_York",
            EventField.DURATION.value: "45",
            EventField.RRULE.value: "FREQ=DAILY;COUNT=2",
            EventField.ID.value: "",
            EventField.PASSWORD.value: "",
            EventField.URL.value: "https://zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1",
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

def test_access_api():
    print("\n=== Testing Access API ===")
    with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api, \
         AccessAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as access_api:
        
        # Create a test user first
        test_user = {
            UserField.NAME.value: "Test Access User",
            UserField.LOGIN.value: "testaccess",
            UserField.PASSWORD.value: "testpass",
            UserField.EMAIL.value: "test@access.com",
            UserField.TIMEZONE.value: 'Australia/Sydney',
        }
        
        try:
            user = user_api.create(test_user)
            user_key = user[UserField.KEY.value]
            print(f"Created test user: {user[UserField.NAME.value]}")
            
            # Test create access with expiry
            expire_after_seconds = 30
            created_access1 = access_api.create({
                AccessField.USER_KEY.value: user_key,
                AccessField.RESOURCE.value: "test-recording",
                AccessField.ACCESS_KEY.value: "testkey123",
                AccessField.ACCESS_TYPE.value: AccessType.HTTP_SERVER_ACCESS,
                EXPIRE_AFTER_SECONDS: expire_after_seconds
            })
            

            print(f"Created access with expires after {expire_after_seconds} seconds: {created_access1}")

            test_access = access_api.validate(created_access1[AccessField.RESOURCE.value], created_access1[AccessField.ACCESS_KEY.value], user_key=user_key)
            print(f"Test access: {test_access}")

            print(f"Sleeping for {expire_after_seconds} seconds...")
            time.sleep(expire_after_seconds)

            test_access = access_api.validate(created_access1[AccessField.RESOURCE.value], created_access1[AccessField.ACCESS_KEY.value], user_key=user_key)
            print(f"Test access: {test_access}")
            
            # Test create with no expiry
            created_access2 = access_api.create({
                AccessField.USER_KEY.value: user_key,
                AccessField.RESOURCE.value: "test-expiry",
                AccessField.ACCESS_KEY.value: "expirekey123",
                AccessField.ACCESS_TYPE.value: AccessType.HTTP_SERVER_ACCESS,
                AccessField.EXPIRES_AT.value: None
            })
            print(f"Created access without expiry: {created_access2}")

            test_access2 = access_api.validate(created_access2[AccessField.RESOURCE.value], created_access2[AccessField.ACCESS_KEY.value], user_key=user_key)
            print(f"Test access without expiry: {test_access2}")   
            
            # Test get
            access_list = access_api.get(filters=[
                [AccessField.USER_KEY.value, '=', user_key],
                [AccessField.RESOURCE.value, '=', 'test-expiry']
            ])
            print(f"Found {len(access_list)} access records for user")
            
            if access_list:
                record = access_list[0]
                resource = record[AccessField.RESOURCE.value]
                access_key = record[AccessField.ACCESS_KEY.value]
                
                # Test update
                updated_access = access_api.update({
                    AccessField.RESOURCE.value: resource,
                    AccessField.ACCESS_KEY.value: access_key,
                    AccessField.ACCESS_TYPE.value: AccessType.HTTP_SERVER_ACCESS,
                    AccessField.EXPIRES_AT.value: (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                })
                print(f"Updated access record: {updated_access}")
                
                # Test delete
                access_api.delete(resource, access_key)
                print(f"Deleted access record with resource '{resource}' and access_key '{access_key}'")
                
                # Verify deleted
                try:
                    access_api.get(filters=[
                        [AccessField.RESOURCE.value, '=', resource],
                        [AccessField.ACCESS_KEY.value, '=', access_key]
                    ])
                    print("Error: Access record still exists after deletion")
                except Exception as e:
                    print("Successfully verified access record deletion")
            
        finally:
            # Clean up test user
            try:
                user_api.delete(user_key)
                print(f"Cleaned up test user: {user_key}")
            except Exception as e:
                print(f"Error cleaning up test user: {str(e)}")

if __name__ == "__main__":
    # main()
    test_access_api()