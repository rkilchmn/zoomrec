import os
import time
from shared.msg_telegram import send_telegram_message
import server.telegram_bot as telegram_bot
from shared.users_api import UserAPI
from shared.users import UserField
# Define constants for the bot token and server details
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')  # Ensure you have the chat ID set in your environment variables

def execute_command():
    """Execute a command to test the bot."""
    # Add a user
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_ADD_USER)
    print(response)

    # Add events
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_ADD_EVENT1)
    print(response)
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_ADD_EVENT2)
    print(response)

    # List users
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_LIST_USER)
    print(response)
    
    # List events
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_LIST_EVENT)
    print(response)
    
    # Modify user
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_MODIFY_USER)
    print(response)
    
    # Modify event
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_MODIFY_EVENT)
    print(response)
    
    # Delete user
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_DELETE_USER)
    print(response)
    
    # Delete event
    response = send_telegram_message(chat_id=TELEGRAM_CHAT_ID, text=telegram_bot.EXAMPLE_DELETE_EVENT)
    print(response)
    
    # Test access commands
    test_access_commands()

def test_access_commands():
    """Test the access-related commands in the Telegram bot."""
    print("\n=== Testing Access Commands ===")
    
    # First, ensure we have a test user
    with UserAPI(
        os.getenv('SERVER_URL', 'http://localhost:8081'),
        os.getenv('SERVER_USERNAME', 'myuser'),
        os.getenv('SERVER_PASSWORD', 'mypassword')
    ) as user_api:
        # Create a test user if it doesn't exist
        test_login = "testaccessuser"
        users = user_api.get(filters=[[UserField.LOGIN.value, '=', test_login]])
        if not users:
            test_user = {
                UserField.NAME.value: "Test Access User",
                UserField.LOGIN.value: test_login,
                UserField.PASSWORD.value: "testpass123",
                UserField.EMAIL.value: "testaccess@example.com",
                UserField.TIMEZONE.value: "UTC"
            }
            user = user_api.create(test_user)
            print(f"Created test user: {user[UserField.NAME.value]}")
    
    # Test add_access
    print("\nTesting /add_access...")
    response = send_telegram_message(
        chat_id=TELEGRAM_CHAT_ID, 
        text=f"{telegram_bot.EXAMPLE_ADD_ACCESS}"
    )
    print(f"Add Access Response: {response}")
    time.sleep(2)  # Give the bot time to process
    
    # Test list_access (page 1)
    print("\nTesting /list_access...")
    response = send_telegram_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"{telegram_bot.EXAMPLE_LIST_ACCESS}"
    )
    print(f"List Access Response: {response}")
    time.sleep(2)
    
    # Test list_access with user filter (for admin)
    print("\nTesting /list_access with user filter...")
    response = send_telegram_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"{telegram_bot.EXAMPLE_LIST_ACCESS_USER}"
    )
    print(f"List Access (User Filter) Response: {response}")
    time.sleep(2)
    
    # Test modify_access (assuming we have an access record with ID 1)
    print("\nTesting /modify_access...")
    response = send_telegram_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"{telegram_bot.EXAMPLE_MODIFY_ACCESS}"
    )
    print(f"Modify Access Response: {response}")
    time.sleep(2)
    
    # Test delete_access (assuming we have an access record with ID 1)
    print("\nTesting /delete_access...")
    response = send_telegram_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"{telegram_bot.EXAMPLE_DELETE_ACCESS}"
    )
    print(f"Delete Access Response: {response}")
    time.sleep(2)

def main():
    """Run the bot."""
    # Start the command execution
    execute_command()

if __name__ == "__main__":
    main() 