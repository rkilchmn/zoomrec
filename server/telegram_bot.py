#!/usr/bin/env python

# pylint: disable=unused-argument, wrong-import-position
from telegram import __version__ as TG_VER
try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}" )
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from datetime import datetime
import os

from shared.events_api import EventAPI
from shared.users_api import UserAPI
from shared.events import Events, EventField, EVENT_DEFAULT_VALUES
from shared.users import MessengerAttribute, Users, UserField, UserRole
from shared.constants import DATE_FORMAT, TIME_FORMAT, DATETIME_FORMAT, LOG_TELEGRAM_BOT_FILENAME, DEBUG_MODULE_TELEGRAM_BOT   
from shared.utilities import start_logging, start_debug

start_logging(LOG_TELEGRAM_BOT_FILENAME)
start_debug(DEBUG_MODULE_TELEGRAM_BOT, os.getenv('DEBUG_PORT_SERVER'))

# get env vars
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SERVER_URL = os.getenv('SERVER_URL')
SERVER_USERNAME = os.getenv('SERVER_USERNAME')
SERVER_PASSWORD = os.getenv('SERVER_PASSWORD')

# telegram bot admin user ids
TELEGRAM_BOT_ADMIN_USERIDS = os.getenv('TELEGRAM_BOT_ADMIN_USERIDS', '')
# Parse admin user IDs into an array once at the beginning
ADMIN_USER_IDS = [str(user_id.strip()) for user_id in TELEGRAM_BOT_ADMIN_USERIDS.split(',') if user_id.strip()] if TELEGRAM_BOT_ADMIN_USERIDS else []

# Define the number of events per page
PAGE_EVENTS = 5

# Define the number of users per page
PAGE_USERS = 5

# Constants for event commands
CMD_ADD_EVENT = "add_event"
CMD_LIST_EVENT = "list_event"
CMD_MODIFY_EVENT = "modify_event"
CMD_DELETE_EVENT = "delete_event"

# Constants for user commands
CMD_ADD_USER = "add_user"
CMD_MODIFY_USER = "modify_user"
CMD_DELETE_USER = "delete_user"
CMD_LIST_USER = "list_user"

# Constants for other commands
CMD_INFO = "info"
CMD_HELP = "help"

# sample requests for events
EXAMPLE_ADD_EVENT1   = f'/{CMD_ADD_EVENT} "important meeting" johndoe 31/12/2025 14:00 America/New_York 60 123456789 mymeetingpassword'
EXAMPLE_ADD_EVENT2   = f'/{CMD_ADD_EVENT} "new year time square" johndoe 31/12/2025 23:45 America/New_York 60 "https://zoom.us/123" "record,transcribe"'
EXAMPLE_LIST_EVENT     = f'/{CMD_LIST_EVENT} "new year time square"'
EXAMPLE_MODIFY_EVENT   = f'/{CMD_MODIFY_EVENT} 2 title "harbour bridge" timezone Australia/Sydney time 23:55'
EXAMPLE_DELETE_EVENT   = f'/{CMD_DELETE_EVENT} "harbour bridge"'

# Usage help for event commands
USAGE_ADD_EVENT =       f"/{CMD_ADD_EVENT} <title> <user login> <date> <time> <timezone> <duration> <id/url> [required with id: <password>] [optional instruction, default is '{EVENT_DEFAULT_VALUES[EventField.INSTRUCTION.value]}']\n" + \
                        f"example: {EXAMPLE_ADD_EVENT1}\n" + \
                        f"example:{EXAMPLE_ADD_EVENT2}"
USAGE_LIST_EVENT =      f"/{CMD_LIST_EVENT} [optional: <page number> or <search term>] - list a particular page if number of events exceeds {PAGE_EVENTS} or provide a search term\n" + \
                        f"example:{EXAMPLE_LIST_EVENT}"
USAGE_MODIFY_EVENT =    f"/{CMD_MODIFY_EVENT} <index or search term> <attribute name1> <new attribute value1> <attribute name2> <new attribute value2> ... Note: search term needs to result in single hit to be processed.\n" + \
                        f"example:{EXAMPLE_MODIFY_EVENT}"
USAGE_DELETE_EVENT =    f"/{CMD_DELETE_EVENT} <index or search term>. Note: search term needs to result in single hit to be processed.\n" + \
                        f"example:{EXAMPLE_DELETE_EVENT}"

# sample requests for events
EXAMPLE_ADD_USER     = f'/{CMD_ADD_USER} "John Doe" johndoe securepassword "john.doe@example.com" "America/New_York" 1'
EXAMPLE_LIST_USER    = f'/{CMD_LIST_USER} johndoe'
EXAMPLE_MODIFY_USER  = f'/{CMD_MODIFY_USER} 1 name "Johnathon Doe" timezone "Australia/Sydney"'
EXAMPLE_DELETE_USER  = f'/{CMD_DELETE_USER} johndoe'

# Usage help for user commands
USAGE_ADD_USER =    f"/{CMD_ADD_USER} <name> <login> <password> [optional: <email> <timezone> <role>]\n" + \
                    f"example: {EXAMPLE_ADD_USER}"

USAGE_LIST_USER =   f"/{CMD_LIST_USER}  <page number> or <search term>] - list a particular page if number of users exceeds {PAGE_EVENTS} or provide a search term\n" + \
                    f"example: {EXAMPLE_LIST_USER}"
USAGE_MODIFY_USER = f"/{CMD_MODIFY_USER} <index> <attribute name1> <new attribute value1> <attribute name2> <new attribute value2> ...\n" + \
                    f"example: {EXAMPLE_MODIFY_USER}"
USAGE_DELETE_USER = f"/{CMD_DELETE_USER} <index>\n" + \
                    f"example: {EXAMPLE_DELETE_USER}"

# Usage help for other commands
USAGE_INFO = f"/{CMD_INFO} - return some session info such as the chat id"

def parse_quoted_args(args):
    """Parse command arguments that may contain quoted strings.
    Returns a list of arguments where quoted strings are treated as single arguments."""

    result = []
    in_quotes = False
    quote_char = ""
    current_arg = []

    for arg in args:
        if not in_quotes and (arg.startswith('"') or arg.startswith("'")):
            in_quotes = True
            quote_char = arg[0]
            if arg.endswith(quote_char) and len(arg) > 1:
                # Handles cases where the argument is a single quoted string
                result.append(arg[1:-1])
                in_quotes = False
            else:
                current_arg.append(arg[1:])  # Remove starting quote
        elif in_quotes:
            if arg.endswith(quote_char):
                current_arg.append(arg[:-1])  # Remove ending quote
                result.append(" ".join(current_arg))
                in_quotes = False
                current_arg = []
            else:
                current_arg.append(arg)
        else:
            result.append(arg)

    # Handle unclosed quotes
    if in_quotes:
        result.append(" ".join(current_arg))
    
    return result
    
    # Handle unclosed quotes by joining remaining args
    if in_quotes:
        result.append(' '.join(current_arg))
    
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text(f"Hi! Use /{CMD_ADD_EVENT} to add a new event, /{CMD_LIST_EVENT} to list events. For further commands and information use /help.")

async def list_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = parse_quoted_args(context.args)
    if len(args) > 1:
        await update.message.reply_text("Usage: " + USAGE_LIST_EVENT)
        return

    try:
        with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
            events_list = event_api.get()
        if not events_list:
            await update.message.reply_text(f"No events found.")
            return
    except Exception as error:
        await update.message.reply_text(f"Error retrieving events: {error}")
        return

    # Filter events based on user permissions
    events_list = filter_events_by_permission(update.effective_user.id, update.effective_chat.id, events_list)

    current_page = 1
    target_indices = list(range(len(events_list))) # default traget list with all events

    if len(args) == 1:  # page or search term
        try:
            current_page = int(args[0])
        except ValueError:
            # not an integer -> search term
            # Call the find method to get the indices of the events
            try:
                target_indices = Events.find(args[0], events_list)
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return
            events_list = [events_list[i] for i in target_indices]  # Keep only the events at target_indices   

    total_events = len(events_list)

    start_index = (current_page - 1) * PAGE_EVENTS
    end_index = min(start_index + PAGE_EVENTS, total_events)
    events_to_display = events_list[start_index:end_index]

    # If there are no events to display for the specified page, send a message accordingly
    if not events_to_display:
        await update.message.reply_text("No events found for the specified page.")
        return

    output = f"List of {total_events} event(s) (Page {current_page}/{(total_events-1)//PAGE_EVENTS + 1}):\n"
    for i, event in enumerate(events_to_display, start=start_index):
        index = target_indices[i]
        output += f"\nEvent {index+1}:\n"

        for field in EventField:  # Iterate over EventField to maintain order
            output += f"  {field.value}: {event[field.value]}\n"

    await update.message.reply_text(output)

async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = parse_quoted_args(context.args)
    if len(args) < 7:
        await update.message.reply_text("Usage: " + USAGE_ADD_EVENT)
        return

    # Retrieve user by login
    try:
        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            user = user_api.get(filters=[[UserField.LOGIN.value,"=",args[1]]])[0] # single user expected
        if not user:
            await update.message.reply_text(f"User with login '{args[1]}' not found.")
            return
    except Exception as error:
        await update.message.reply_text(f"Error retrieving user: {error}")
        return

    # Initialize the event dictionary
    event = {}

    # Validate and parse date and time
    try:
        date = datetime.strptime(args[2], DATE_FORMAT).date()  # Parse the date
        time = datetime.strptime(args[3], TIME_FORMAT).time()  # Parse the time
        event[EventField.DTSTART.value] = datetime.combine(date, time).strftime(DATETIME_FORMAT).lower()  # Combine into dtstart
    except ValueError as e:
        await update.message.reply_text(f"Invalid date or time format: {e}")
        return

    # Set other event attributes directly
    event[EventField.TITLE.value] = args[0]
    event[EventField.TIMEZONE.value] = args[4]
    event[EventField.DURATION.value] = args[5]
    event[EventField.USER_KEY.value] = user[UserField.KEY.value]  # Set user_key from retrieved user

    # Validate id and set password and instruction
    if args[6].startswith("http"):
        event[EventField.URL.value] = args[6]
        event[EventField.ID.value] = ""
        event[EventField.PASSWORD.value] = ""
        instructionArgNo = 7  # password was skipped
    else:
        event[EventField.ID.value] = args[6]
        event[EventField.PASSWORD.value] = args[7]
        event[EventField.URL.value] = ""
        instructionArgNo = 8  # last arg is instruction (unless URL is provided)

    if (len(args) - 1) == instructionArgNo:
        event[EventField.INSTRUCTION.value] = args[instructionArgNo]

    try:
        with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
            created_event = event_api.create(event)
        await update.message.reply_text(f"Created {Events.nameStr(created_event)}")
    except Exception as error:
        await update.message.reply_text(f"Error adding event: {error}")

async def modify_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = parse_quoted_args(context.args)
        if not args:
            await update.message.reply_text("Usage: " + USAGE_MODIFY_EVENT)
            return

        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                events_list = event_api.get()
            if not events_list:
                await update.message.reply_text(f"No events found.")
                return
        except Exception as error:
            await update.message.reply_text(f"Error retrieving events: {error}")
            return

        # Filter events based on user permissions
        events_list = filter_events_by_permission(update.effective_user.id, update.effective_chat.id, events_list)

        # Determine if the first argument is an index or a search term
        if args[0].isdigit() and int(args[0]) <= 99:
            index = int(args[0])
            if index < 1 or index > len(events_list):
                await update.message.reply_text(f"Index {index} is out of range. Please provide a valid index.")
                return
            target_index = index - 1  # Adjust for 0-based index
        else:
            # Find target event to process using search term
            try:
                target_indices = Events.find(args[0], events_list)
                if len(target_indices) != 1:
                    raise ValueError(f"Expected exactly 1 match, but found {len(target_indices)}. Please refine your search.")
                target_index = target_indices[0]
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return

        if len(args) < 3 or len(args) % 2 != 1:
            await update.message.reply_text("Usage: " + USAGE_MODIFY_EVENT)
            return

        # Initialize variables for date and time updates
        new_date = None
        new_time = None
        target_event = events_list[target_index]
        for i in range(1, len(args), 2):
            attribute_name = args[i]
            new_attribute_value = args[i + 1]

            if attribute_name.lower() == "date":
                new_date = new_attribute_value
            elif attribute_name.lower() == "time":
                new_time = new_attribute_value
            elif attribute_name.lower() not in target_event:
                await update.message.reply_text(f"Attribute '{attribute_name}' not found in event")
                return
            else:
                target_event[attribute_name] = new_attribute_value

        # Update dtstart if date or time is provided
        if new_date or new_time:
            try:
                # Parse the existing dtstart
                existing_dtstart = datetime.strptime(target_event[EventField.DTSTART.value], DATETIME_FORMAT)

                # Update the date if provided
                if new_date:
                    date_obj = datetime.strptime(new_date, DATE_FORMAT).date()
                    existing_dtstart = existing_dtstart.replace(year=date_obj.year, month=date_obj.month, day=date_obj.day)

                # Update the time if provided
                if new_time:
                    time_obj = datetime.strptime(new_time, TIME_FORMAT).time()
                    existing_dtstart = existing_dtstart.replace(hour=time_obj.hour, minute=time_obj.minute)

                # Set the updated dtstart back to the event
                target_event[EventField.DTSTART.value] = existing_dtstart.strftime(DATETIME_FORMAT)

            except ValueError as e:
                await update.message.reply_text(f"Invalid date or time format: {e}")
                return

        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                event_api.update(target_event)
            await update.message.reply_text(f"Attributes successfully modified for {Events.nameStr(target_event)} with index {target_index + 1}")
        except Exception as error:
            await update.message.reply_text(f"Error updating event: {error}")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = parse_quoted_args(context.args)
        if not args:
            await update.message.reply_text("Usage: " + USAGE_DELETE_EVENT)
            return

        try:
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                events_list = event_api.get()
            if not events_list:
                await update.message.reply_text(f"No events found.")
                return
        except Exception as error:
            await update.message.reply_text(f"Error retrieving events: {error}")
            return

        # Filter events based on user permissions
        events_list = filter_events_by_permission(update.effective_user.id, update.effective_chat.id, events_list)

        # Determine if the first argument is an index or a search term
        if args[0].isdigit() and int(args[0]) <= 99:
            index = int(args[0])
            if index < 1 or index > len(events_list):
                await update.message.reply_text(f"Index {index} is out of range. Please provide a valid index.")
                return
            target_index = index - 1  # Adjust for 0-based index
        else:
            # Find target event to process using search term
            try:
                target_indices = Events.find(args[0], events_list)
                if len(target_indices) != 1:
                    raise ValueError(f"Expected exactly 1 match, but found {len(target_indices)}. Please refine your search.")
                target_index = target_indices[0]
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return

        try:
            target_event = events_list[target_index]
            with EventAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as event_api:
                event_api.delete(target_event[EventField.KEY.value])
            await update.message.reply_text(f"Deleted {Events.nameStr(target_event)} successfully")
        except Exception as error:
            await update.message.reply_text(f"Error deleting event: {error}")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# User management commands
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = parse_quoted_args(context.args)
        if len(args) < 3:
            await update.message.reply_text("Usage: " + USAGE_ADD_USER)
            return

        user = {
            UserField.NAME.value: args[0],
            UserField.LOGIN.value: args[1],
            UserField.PASSWORD.value: args[2],
            UserField.EMAIL.value: args[3] if len(args) > 3 else None,
            UserField.TIMEZONE.value: args[4] if len(args) > 4 else None,
            UserField.ROLE.value: int(args[5]) if len(args) > 5 else None
        }

        # add telegram client id 
        Users.set_messenger_attribute( messenger_attribute=MessengerAttribute.TELEGRAM_CHAT_ID, user=user, value=update.message.from_user.id)
    
        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            created_user = user_api.create(user)
        await update.message.reply_text(f"Created {Users.nameStr(created_user)}")
    except Exception as error:
        await update.message.reply_text(f"Error adding user: {error}")

async def modify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = parse_quoted_args(context.args)
        if len(args) < 3 or len(args) % 2 != 1:
            await update.message.reply_text("Usage: " + USAGE_MODIFY_USER)
            return

        try:
            with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                user_list = user_api.get()
            if not user_list:
                await update.message.reply_text(f"No users found.")
                return        
        except Exception as error:
            await update.message.reply_text(f"Error retrieving users: {error}")
            return

        # Filter users based on user permissions
        user_list = filter_users_by_permission(update.effective_user.id, update.effective_chat.id, user_list)
        if not user_list:
            await update.message.reply_text(f"No users found that you have permission to modify.")
            return

        # Determine if the first argument is an index or a search term
        if args[0].isdigit() and int(args[0]) <= 99:
            index = int(args[0])
            if index < 1 or index > len(user_list):
                await update.message.reply_text(f"Index {index} is out of range. Please provide a valid index.")
                return
            target_index = index - 1  # Adjust for 0-based index
        else:
            # Find target event to process using search term
            try:
                target_indices = Users.find(args[0], user_list)
                if len(target_indices) != 1:
                    raise ValueError(f"Expected exactly 1 match, but found {len(target_indices)}. Please refine your search.")
                target_index = target_indices[0]
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return

        target_user = user_list[target_index]
        for i in range(1, len(args), 2):
            attribute_name = args[i]
            new_attribute_value = args[i + 1]
            if attribute_name.lower() not in target_user:
                await update.message.reply_text(f"Attribute '{attribute_name}' not found in user")
                return
            target_user[attribute_name] = new_attribute_value

        try:
            with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                user_api.update(target_user)
            await update.message.reply_text(f"Attributes successfully modified for {Users.nameStr(target_user)} with index {target_index + 1}")
        except Exception as error:
            await update.message.reply_text(f"Error updating user: {error}")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        args = parse_quoted_args(context.args)
        if len(args) != 1:
            await update.message.reply_text("Usage: " + USAGE_DELETE_USER)
            return

        try:
            with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                user_list = user_api.get()
            if not user_list:
                await update.message.reply_text(f"No users found.")
                return        
        except Exception as error:
            await update.message.reply_text(f"Error retrieving users: {error}")
            return

        # Filter users based on user permissions
        user_list = filter_users_by_permission(update.effective_user.id, update.effective_chat.id, user_list)
        if not user_list:
            await update.message.reply_text(f"No users found that you have permission to delete.")
            return

        # Determine if the first argument is an index or a search term
        if args[0].isdigit() and int(args[0]) <= 99:
            index = int(args[0])
            if index < 1 or index > len(user_list):
                await update.message.reply_text(f"Index {index} is out of range. Please provide a valid index.")
                return
            target_index = index - 1  # Adjust for 0-based index
        else:
            # Find target event to process using search term
            try:
                target_indices = Users.find(args[0], user_list)
                if len(target_indices) != 1:
                    raise ValueError(f"Expected exactly 1 match, but found {len(target_indices)}. Please refine your search.")
                target_index = target_indices[0]
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return

        target_user = user_list[target_index]
        try:
            with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                user_api.delete(target_user[UserField.KEY.value])
            await update.message.reply_text(f"Deleted {Users.nameStr(target_user)} with index {target_index + 1}.")
        except Exception as error:
            await update.message.reply_text(f"Error deleting user: {error}")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def list_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = parse_quoted_args(context.args)
    if len(args) > 1:
        await update.message.reply_text("Usage: " + USAGE_LIST_USER)
        return
    try:
        # get all users
        with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
            users = user_api.get()
            if not users:
                await update.message.reply_text(f"No users found.")
                return
            
        # Filter users based on user permissions
        users = filter_users_by_permission(update.effective_user.id, update.effective_chat.id, users)
        if not users:
            await update.message.reply_text(f"No users found that you have permission to view.")
            return
    except Exception as error:
        await update.message.reply_text(f"Error retrieving users: {error}")
        return
    
    current_page = 1
    target_indices = list(range(len(users)))  # default target list with all users

    if len(args) == 1:  # page or search term
        try:
            current_page = int(args[0])
        except ValueError:
            # not an integer -> search term
            # Call the find method to get the indices of the users
            try:
                target_indices = Users.find(args[0], users)
            except ValueError as error:
                await update.message.reply_text(f"Error: {str(error)}")
                return
            users = [users[i] for i in target_indices]  # Keep only the users at target_indices

    total_users = len(users)

    start_index = (current_page - 1) * PAGE_USERS
    end_index = min(start_index + PAGE_USERS, total_users)
    users_to_display = users[start_index:end_index]

    # If there are no users to display for the specified page, send a message accordingly
    if not users_to_display:
        await update.message.reply_text("No users found for the specified page.")
        return

    output = f"List of {total_users} user(s) (Page {current_page}/{(total_users-1)//PAGE_USERS + 1}):\n"
    for i, user in enumerate(users_to_display, start=start_index):
        index = target_indices[i]
        output += f"\nUser {index+1}:\n"
        for field in UserField:  # Iterate over EventField to maintain order
            output += f"  {field.value}: {user[field.value]}\n"

    await update.message.reply_text(output)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    response = f"Use these commands to manage events:\n"
    response += f"{USAGE_ADD_EVENT}\n"
    response += f"{USAGE_LIST_EVENT}\n"
    response += f"{USAGE_MODIFY_EVENT}\n"
    response += f"{USAGE_DELETE_EVENT}\n"
    response += f"\n"
    response += f"Use these commands to manage users:\n"
    response += f"{USAGE_ADD_USER}\n"
    response += f"{USAGE_LIST_USER}\n"
    response += f"{USAGE_MODIFY_USER}\n"
    response += f"{USAGE_DELETE_USER}\n"
    response += f"{USAGE_INFO}\n"
    await update.message.reply_text(response)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /info is issued."""
    chat_id = update.effective_chat.id
    response = f"Chat ID: {chat_id}"

    await update.message.reply_text(response)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Invalid command. Use /help to see a list of available commands.")

# Helper function to check if a user is an admin
def is_admin(user_id):
    return str(user_id) in ADMIN_USER_IDS

# Helper function to filter events based on user permissions
def filter_events_by_permission(user_id, chat_id, events_list):
    # If user is admin, return all events
    if is_admin(user_id):
        return events_list
    
    # For non-admin users, filter events based on telegram chat ID
    filtered_events = []
    
    for event in events_list:
        try:
            # Get the user associated with this event
            user_filters = [[UserField.KEY.value, "=", event[EventField.USER_KEY.value]]]
            with UserAPI(SERVER_URL, SERVER_USERNAME, SERVER_PASSWORD) as user_api:
                user_list = user_api.get(filters=user_filters)
            
            if user_list and len(user_list) > 0:
                user = user_list[0]
                # Check if the telegram chat ID matches
                telegram_chat_id = Users.get_messenger_attribute(MessengerAttribute.TELEGRAM_CHAT_ID, user)
                if telegram_chat_id and str(telegram_chat_id) == str(chat_id):
                    filtered_events.append(event)
        except Exception as e:
            logging.error(f"Error filtering event {event.get(EventField.KEY.value, 'unknown')}: {str(e)}", exc_info=True)
    
    return filtered_events

# Helper function to filter users based on user permissions
def filter_users_by_permission(user_id, chat_id, users_list):
    # If user is admin, return all users
    if is_admin(user_id):
        return users_list
    
    # For non-admin users, filter users based on telegram chat ID
    filtered_users = []
    
    for user in users_list:
        try:
            # Check if the telegram chat ID matches
            telegram_chat_id = Users.get_messenger_attribute(MessengerAttribute.TELEGRAM_CHAT_ID, user)
            if telegram_chat_id and str(telegram_chat_id) == str(chat_id):
                filtered_users.append(user)
        except Exception as e:
            logging.error(f"Error filtering user {user.get(UserField.KEY.value, 'unknown')}: {str(e)}", exc_info=True)
    
    return filtered_users

def start_bot() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # on different commands - answer in Telegram

    # Add the handlers for the different commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(CMD_ADD_EVENT, add_event))
    application.add_handler(CommandHandler(CMD_LIST_EVENT, list_event))
    application.add_handler(CommandHandler(CMD_MODIFY_EVENT, modify_event))
    application.add_handler(CommandHandler(CMD_DELETE_EVENT, delete_event))
    application.add_handler(CommandHandler(CMD_ADD_USER, add_user))
    application.add_handler(CommandHandler(CMD_MODIFY_USER, modify_user))
    application.add_handler(CommandHandler(CMD_DELETE_USER, delete_user))
    application.add_handler(CommandHandler(CMD_LIST_USER, list_user))
    application.add_handler(CommandHandler(CMD_HELP, help_command))
    application.add_handler(CommandHandler(CMD_INFO, info_command))

    # Add handler for unknown commands (must be added after all other command handlers)
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    # on non command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    # Run the bot until the user presses Ctrl-C
    while True:
        try:
            application.run_polling()
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                # Exit the program if the exception is a KeyboardInterrupt
                return
            elif isinstance(e, NetworkError):
                logging.error(f"Network error: {str(e)}")
                continue
            else:
                raise e # will be caucht be exception handler and added to log

if __name__ == "__main__":
    if not (TELEGRAM_BOT_TOKEN and SERVER_URL and SERVER_USERNAME and SERVER_PASSWORD):
        print("Telegram token, server URL, username, or password is missing. No Telegram bot will be started!")
    else:
        start_bot()
