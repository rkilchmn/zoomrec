#!/usr/bin/env python

# pylint: disable=unused-argument, wrong-import-position
import sys
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
from events import read_events_from_csv, write_events_to_csv, validate_event, find_event, remove_past_events,set_telegramchatid

global CSV_PATH
global TELEGRAM_TOKEN

# Define the number of events per page
PAGE_EVENTS = 10


USAGE_ADD = "/add <description> <weekday> <time> <timezone> <duration> <id/url> [required with id: <password>] [optional, default is 'true': <record>]\n" + \
            "example: /add important_meeting tuesday 14:00 America/New_York 60 123456789 secret_passwd true\n" + \
            "example: /add new_year_time_square 31/12/2023 23:45 America/New_York 60 https://zoom.us?123...ASE\n"
USAGE_FIND = "/find <index or part of description>] - list matching event\n"
USAGE_LIST = f"/list [optional: page <index>] - list a particular page if number of events exceeds {PAGE_EVENTS}\n"
USAGE_MODIFY = "/modify <index or part of description> <attribute name1> <new attribute value1> <attribute name2> <new attribute value2> ..."
USAGE_DELETE = "/delete <index or part of description>"
USAGE_INFO = "/info - return some session info such as the chat id"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text("Hi! Use /add to add a new event, /list to list events, /modify to modify an event, and /delete to delete an event. Use /help for further information.")

async def find_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: " + USAGE_FIND)
        return
    events = read_events_from_csv( CSV_PATH)

    target_index = ''
    if len(args) == 1:
        try:
            target_index = find_event(context.args[0], events)
        except ValueError as error:
            await update.message.reply_text( error.args[0])
            return

    output = "List of events:\n"
    for i, event in enumerate(events):
        i += 1
        if target_index:
            if i != target_index+1:
                continue
            
        output += f"Event {i}\n"
        output += f"  description : {event['description']}\n"
        for attribute_name, attribute_value in event.items():
            if attribute_name == 'description':
                continue
            output += f"  {attribute_name} : {attribute_value}\n"
    await update.message.reply_text(output)

async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    args = context.args
    if len(args) == 1 or len(args) > 2:
        await update.message.reply_text("Usage: " + USAGE_LIST)
        return

    events = read_events_from_csv(CSV_PATH)
    total_events = len(events)
    current_page = 1
        
    if len(args) == 2:
        # Get the current page number from the user's input (default to 1 if not provided or invalid)
        if args[0].lower() == "page":
            try:
                current_page = int(args[1])
            except ValueError:
                await update.message.reply_text("Invalid page number. Please enter a valid page number: /list page <number>.")
                return
        else:
            await update.message.reply_text("Usage: " + USAGE_LIST)
            return

    start_index = (current_page - 1) * PAGE_EVENTS
    end_index = min(start_index + PAGE_EVENTS, total_events)
    events_to_display = events[start_index:end_index]

    # If there are no events to display for the specified page, send a message accordingly
    if not events_to_display:
        await update.message.reply_text("No events found for the specified page.")

    output = f"List of {total_events} event(s) (Page {current_page}/{(total_events-1)//PAGE_EVENTS + 1}):\n"
    for i, event in enumerate(events_to_display, start=start_index):
        i += 1
        output += f"Event {i}\n"
        output += f"  description : {event['description']}\n"
        for attribute_name, attribute_value in event.items():
            if attribute_name == 'description':
                continue
            output += f"  {attribute_name} : {attribute_value}\n"

    await update.message.reply_text(output)


async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH

    """Add a new event to the meeting.csv file."""
    args = context.args
    if len(args) < 6:
        await update.message.reply_text("Usage: " + USAGE_ADD)
        return

    recordArgNo = 7 # last arg is record (unless URL is provided - see following)
    # Validate id
    if args[5].startswith("http"):
        password = ""
        recordArgNo = 6 # password was skipped
    else:    
        password = args[6]

    if (len(args)-1) == recordArgNo: 
        record = args[recordArgNo]
    else: # omitted as its optional
        record = 'true' # default

    event = {'description': args[0], 'weekday': args[1].lower(), 'time': args[2], 
             'timezone': args[3], 'duration': args[4], 'id': args[5], 'password': password, 
             'record': record, 'user' : set_telegramchatid( update.effective_chat.id)}

    try:
        event = validate_event( event)
    except ValueError as error:
        await update.message.reply_text( error.args[0])
        return

    events = read_events_from_csv(CSV_PATH)
    events = remove_past_events( events)
    events.append(event)
    write_events_to_csv(CSV_PATH, events)
    await update.message.reply_text(f"Event with description '{args[0]}' added successfully!")


async def modify_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    try:
        if not context.args:
            await update.message.reply_text("Usage: " + USAGE_MODIFY)
            return

        events = read_events_from_csv(CSV_PATH)

        # find target event to process
        try:
            target_index = find_event(context.args[0], events)
            target_event = events[target_index]
        except ValueError as error:
            await update.message.reply_text( error.args[0])
            return

        if len(context.args) < 3 or len(context.args) % 2 != 1:
            await update.message.reply_text("Usage: " + USAGE_MODIFY)
            return

        for i in range(1, len(context.args), 2):
            attribute_name = context.args[i]
            new_attribute_value = context.args[i + 1]
            if attribute_name.lower() not in target_event:
                await update.message.reply_text(f"Attribute '{attribute_name}' not found in event")
                return

            if attribute_name in ['weekday']:    
                target_event[attribute_name] = new_attribute_value.lower()
            else:
                target_event[attribute_name] = new_attribute_value

        try:
            target_event = validate_event( target_event)
        except ValueError as error:
            await update.message.reply_text( error.args[0])
            return

        events[target_index] = target_event
        write_events_to_csv(CSV_PATH, events)
        events[target_index] = target_event
        await update.message.reply_text(f"Attributes successfully modified for event '{target_event['description']}' with index {target_index+1}")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    try:
        if not context.args:
            await update.message.reply_text("Usage: " + USAGE_DELETE)
            return
        events = read_events_from_csv(CSV_PATH)
       
        # find target event to process
        try:
            target_index = find_event(context.args[0], events)
            target_event = events[target_index]
        except ValueError as error:
            await update.message.reply_text( error.args[0])
            return

        del events[target_index]
        write_events_to_csv(CSV_PATH, events)
        await update.message.reply_text(f"Event '{target_event['description']}' with index {target_index+1} successfully deleted")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    response = "Use these commands to manage events:\n"
    response += USAGE_ADD + "\n"
    response += USAGE_LIST + "\n"
    response += USAGE_FIND + "\n"
    response += USAGE_MODIFY + "\n"
    response += USAGE_DELETE + "\n"
    response += USAGE_INFO + "\n"
    await update.message.reply_text(response)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /info is issued."""
    chat_id = update.effective_chat.id
    response = f"Chat ID: {chat_id}"

    await update.message.reply_text(response)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Invalid command. Use /help to see a list of available commands.")

def start_bot( csv_path, telegram_token) -> None:
    global CSV_PATH
    global TELEGRAM_TOKEN

    CSV_PATH = csv_path
    TELEGRAM_TOKEN = telegram_token

    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # on different commands - answer in Telegram

    # Add the handlers for the different commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_event))
    application.add_handler(CommandHandler("list", list_events))
    application.add_handler(CommandHandler("find", find_events))
    application.add_handler(CommandHandler("modify", modify_event))
    application.add_handler(CommandHandler("delete", delete_event))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))

     # on non command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    # Run the bot until the user presses Ctrl-C
    while True:
        try:
            application.run_polling()
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                # Exit the program if the exception is a KeyboardInterrupt
                raise e

if __name__ == "__main__":
    start_bot( csv_path = sys.argv[1], telegram_token = sys.argv[2])
