import os
from msg_telegram import send_telegram_message
import telegram_bot

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

def main():
    """Run the bot."""
    # Start the command execution
    execute_command()

if __name__ == "__main__":
    main() 