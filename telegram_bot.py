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
USAGE_MODIFY = "/modify <index or part of description> <attribute name1> <new attribute value1> <attribute name2> <new attribute value2> ..."
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

def validate_event(event):

    if event['weekday']:
         # Validate weekday
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if event['weekday'].lower() not in weekdays:
            return f"Invalid weekday '{event['weekday']}'. Use only: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday."
    else:
        return "Missing attribute weekday."

    if event['time']:
        # Validate time
        try:
            time.strptime(event['time'], '%H:%M')
        except ValueError:
            return f"Invalid time format '{event['time']}'. Use HH:MM format."
    else:
        return "Missing attribute time."

    if event['duration']:
    # Validate duration
        try:
            duration = int(event['duration'])
            if duration <= 0:
                return f"Invalid duration '{duration}'. Duration must be a positive number of minutes."
        except ValueError:
            return f"Invalid duration '{duration}'. Duration must be a number of minutes."
    else:
        return "Missing attribute duration"
            
    # Validate id
    if event['id']:
        if event['id'].startswith("https://"):
            if not validators.url(event['id']):
                return "Invalid URL format."
        else:    
            if not re.search( r'\d{9,}', event['id']):
                return "Invalid id. If id starts with 'https://' then it must be a URL, otherwise it must be a number with minimum 9 digits (no blanks)"
                
            if not event['password']:
                return "Password cannot be empty."
    else:
        return "Missing attribute id."

    # Validate record
    if event['record']:
        if event['record'].lower() not in ["true", "false"]:
            return f"Invalid record '{event['record']}'. Record must be either 'true' or 'false'"
    else:
        return "Missing attribute record."

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

    recordArgNo = 6 # last arg is record (unless URL is provided - see following)
    # Validate id
    if args[4].startswith("https://"):
        password = ""
        recordArgNo = 5 # password was skipped
    else:    
        password = args[5]

    if (len(args)-1) != recordArgNo: # not enough args
        await update.message.reply_text("Record missing. Record must be either 'true' or 'false'")
        return
    record = args[recordArgNo]

    events = read_events_from_csv(CSV_PATH)
    event = {'description': args[0], 'weekday': args[1].lower(), 'time': args[2], 'duration': args[3], 'id': args[4], 'password': password, 'record': record}

    validation_error = validate_event( event)
    if validation_error:
        await update.message.reply_text(validation_error)
        return

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
        target_event = None
        try:
            # Try to interpret the argument as an index (index starts with 1)
            target_index = int(context.args[0]) - 1
            target_event = events[target_index]
        except ValueError:
            # If it's not an index, search for an event whose description contains the argument
            target_desc = context.args[0].lower()
            hits = 0
            for i, event in enumerate(events):
                if target_desc in event['description'].lower():
                    target_event = event
                    target_index = i
                    hits += 1

            if hits > 1 :
                await update.message.reply_text(f"{hits} event found with description '{context.args[0]}'. Please make it unique such that only 1 event matches.")
                return

        if target_event is None:
            await update.message.reply_text(f"No event found with description or index '{context.args[0]}'")
            return
        
       

        if len(context.args) < 3 or len(context.args) % 2 != 1:
            await update.message.reply_text("Usage: " + USAGE_MODIFY)
            return

        for i in range(1, len(context.args), 2):
            attribute_name = context.args[i]
            new_attribute_value = context.args[i + 1]
            if attribute_name not in target_event:
                await update.message.reply_text(f"Attribute '{attribute_name}' not found in event")
                return

            if attribute_name in ['weekday']:    
                target_event[attribute_name] = new_attribute_value.lower()
            else:
                target_event[attribute_name] = new_attribute_value

        validation_error = validate_event( target_event)
        if validation_error:
            await update.message.reply_text(validation_error)
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
        target_event = None
        try:
            # Try to interpret the argument as an index
            target_index = int(context.args[0]) -1 
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
        await update.message.reply_text(f"Event '{target_event['description']}' with index {target_index+1} successfully deleted")
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
