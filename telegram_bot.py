#!/usr/bin/env python

# pylint: disable=unused-argument, wrong-import-position
import sys
import csv
import time
import re
import validators
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

global CSV_PATH
global CSV_DELIMITER
global TELEGRAM_TOKEN


USAGE_ADD = "/add <description> <weekday> <time> <duration> <id> <password> <record> or\n" + \
            "/add <description> <weekday> <time> <duration> <url> <record>\n" + \
            "example: /add important_meeting tuesday 14:00 60 123456789 secret_passwd true"
USAGE_LIST = "/list - list all events"
USAGE_MODIFY = "/modify <index or part of description> <attribute name> <new attribute value>"
USAGE_DELETE = "/delete <index or part of description>"

def read_events_from_csv(file_name):
    global CSV_DELIMITER
    events = []
    with open(file_name, 'r') as file:
        reader = csv.reader(file,delimiter=CSV_DELIMITER)
        headers = next(reader)
        for row in reader:
            event = {headers[i]: row[i] for i in range(len(headers))}
            events.append(event)
    return events

def write_events_to_csv(file_name, events):
    global CSV_DELIMITER
    with open(file_name, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['weekday', 'time', 'duration', 'id', 'password', 'description', 'record'], delimiter=CSV_DELIMITER)
        writer.writeheader()
        for event in events:
            writer.writerow(event)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text("Hi! Use /add to add a new event, /list to list events, /modify to modify an event, and /delete to delete an event. Use /help for further information.")

async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    args = context.args
    if len(args) != 0:
        await update.message.reply_text("Usage: " + USAGE_LIST)
        return
    events = read_events_from_csv( CSV_PATH)
    output = "List of events:\n"
    for i, event in enumerate(events):
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
    # Validate weekday
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if args[1].lower() not in weekdays:
        await update.message.reply_text("Invalid weekday. Use only: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday")
        return

    # Validate time
    try:
        time.strptime(args[2], '%H:%M')
    except ValueError:
        await update.message.reply_text("Invalid time format. Use HH:MM")
        return

    # Validate duration
    try:
        duration = int(args[3])
        if duration <= 0:
            await update.message.reply_text("Invalid duration. Duration must be a positive number")
            return
    except ValueError:
        await update.message.reply_text("Invalid duration. Duration must be a number")
        return

    recordArgNo = 6 # last arg is record (unless URL is provided - see following)
    # Validate id
    if args[4].startswith("https://"):
        if not validators.url(args[4]):
            await update.message.reply_text("Invalid URL format")
            return
        password = ""
        recordArgNo = 5 # password was skipped
    else:
        
        if not re.search( r'\d{9,}', args[4]):
            await update.message.reply_text("Invalid id. If id starts with 'https://' then it must be a URL, otherwise it must be a number with minimum 9 digits (no blanks)")
            return
        if not args[5]:
            await update.message.reply_text("Password cannot be empty")
            return
        password = args[5]
    # Validate record
    if (len(args)-1) != recordArgNo: # not enough args
        await update.message.reply_text("Record missing. Record must be either 'true' or 'false'")
        return
    if args[recordArgNo].lower() not in ["true", "false"]:
        await update.message.reply_text("Invalid record. Record must be either 'true' or 'false'")
        return
    record = args[recordArgNo].lower() == "true"

    events = read_events_from_csv(CSV_PATH)
    event = {'description': args[0], 'weekday': args[1].lower(), 'time': args[2], 'duration': args[3], 'id': args[4], 'password': password, 'record': record}
    events.append(event)
    write_events_to_csv(CSV_PATH, events)
    await update.message.reply_text(f"Event with description '{args[0]}' added successfully!")


async def modify_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    try:
        if not context.args:
            await update.message.reply_text("Usage: " + USAGE_MODIFY)
            return

        events = read_events_from_csv( CSV_PATH)
        target_event = None
        try:
            # Try to interpret the argument as an index
            target_index = int(context.args[0])
            target_event = events[target_index]
        except ValueError:
            # If it's not an index, search for an event whose description contains the argument
            target_desc = context.args[0].lower()
            for i, event in enumerate(events):
                if target_desc in event['description'].lower():
                    target_event = event
                    target_index = i
                    break

        if target_event is None:
            await update.message.reply_text(f"No event found with description or index '{context.args[0]}'")
            return

        if len(context.args) < 3:
            await update.message.reply_text("Usage: /modify <index or part of description> <attribute name> <new attribute value>")
            return

        attribute_name = context.args[1]
        new_attribute_value = ' '.join(context.args[2:])

        if attribute_name not in target_event:
            await update.message.reply_text(f"Attribute '{attribute_name}' not found in event")
            return

        target_event[attribute_name] = new_attribute_value
        events[target_index] = target_event
        write_events_to_csv(CSV_PATH, events)
        await update.message.reply_text(f"Attribute '{attribute_name}' in event with index {target_index} successfully modified")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global CSV_PATH
    try:
        if not context.args:
            await update.message.reply_text("Usage: " + USAGE_DELETE)
            return
        events = read_events_from_csv(CSV_PATH)
        target_event = None
        try:
            # Try to interpret the argument as an index
            target_index = int(context.args[0])
            target_event = events[target_index]
        except ValueError:
            # If it's not an index, search for an event whose description contains the argument
            target_desc = context.args[0].lower()
            for i, event in enumerate(events):
                if target_desc in event['description'].lower():
                    target_event = event
                    target_index = i
                    break

        if target_event is None:
            await update.message.reply_text(f"No event found with description or index '{context.args[0]}'")
            return

        del events[target_index]
        write_events_to_csv(CSV_PATH, events)
        await update.message.reply_text(f"Event with index {target_index} successfully deleted")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    response = "Use these commands to manage events:\n"
    response += USAGE_ADD + "\n"
    response += USAGE_LIST + "\n"
    response += USAGE_MODIFY + "\n"
    response += USAGE_DELETE + "\n"
    await update.message.reply_text(response)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Invalid command. Use /help to see a list of available commands.")

def start_bot( csv_path, csv_delimiter, telegram_token) -> None:
    global CSV_PATH
    global CSV_DELIMITER
    global TELEGRAM_TOKEN

    CSV_PATH = csv_path
    CSV_DELIMITER = csv_delimiter
    TELEGRAM_TOKEN = telegram_token

    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # on different commands - answer in Telegram

    # Add the handlers for the different commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_event))
    application.add_handler(CommandHandler("list", list_events))
    application.add_handler(CommandHandler("modify", modify_event))
    application.add_handler(CommandHandler("delete", delete_event))
    application.add_handler(CommandHandler("help", help_command))

     # on non command
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    start_bot( csv_path = sys.argv[1], csv_delimiter = ';', telegram_token = sys.argv[2])
