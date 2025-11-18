from doctest import debug
from flask import Flask, request, jsonify, send_file, Response, abort, render_template_string
from flask_basicauth import BasicAuth
from datetime import datetime, timezone, timedelta
import os.path
import glob
from typing import Any, Dict, List, Optional, Set, TypeVar, Union, Tuple
from shared.events import Events, EventStatus, EventField, SQLLiteEvents, EventType
from urllib.parse import unquote, quote
from shared.users import SQLLiteUser, Users, UserField
from shared.access import SQLLiteAccess, AccessField, AccessType, Access
from shared import constants
import logging
import json
import mimetypes

from shared.utilities import start_debug

def parse_filter_parameters(request_args) -> List[List[Optional[str]]]:
    """Parse filter parameters from request arguments.
    
    Returns a list of filters where each filter is [Name, Operator, Value].
    """
    filters = []
    
    # Retrieve filter parameters from the request
    for key, value in request_args.items():
        if key.startswith("Filter."):
            # Extract the filter index
            parts = key.split('.')
            if len(parts) == 3:  # Ensure we have the correct format
                index = parts[1]
                if len(filters) < int(index):  # Ensure the filters list is long enough
                    filters.append([None, None, None])  # Initialize with None
                if parts[2] == "Name":
                    filters[int(index) - 1][0] = value  # Set attribute
                elif parts[2] == "Operator":
                    filters[int(index) - 1][1] = value  # Set operator
                elif parts[2] == "Value":
                    filters[int(index) - 1][2] = value  # Set value
    
    return filters
from shared.arduino_utils import (
    parse_version_string, get_config_file_path, find_compatible_firmware,
    ERROR_CONFIG_DIR_NOT_FOUND, ERROR_CONFIG_DIR_READ, ERROR_NO_COMPATIBLE_CONFIG,
    ERROR_NO_CONFIG_FILES, ERROR_NO_VALID_CONFIG_FILES, ERROR_CONFIG_READ,
    ERROR_NO_NEWER_CONFIG, ERROR_FIRMWARE_DIR_NOT_FOUND,
    ERROR_NO_COMPATIBLE_FIRMWARE, ERROR_INVALID_FIRMWARE_VERSION, ERROR_UNEXPECTED
)

start_debug(constants.DEBUG_MODULE_ZOOMREC_SERVER_APP, os.getenv('DEBUG_PORT_SERVER'))

app = Flask(__name__)

# Configure logging
if __name__ != '__main__':
    # ------------------------------
    # Running under Gunicorn
    # ------------------------------
    gunicorn_logger = logging.getLogger('gunicorn.error')

    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
        app.logger.propagate = False

else:
    # ------------------------------
    # Running standalone (python app.py)
    # ------------------------------
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.StreamHandler()]
    )

BASE_PATH = os.getenv('ZOOMREC_HOME')
ZOOMREC_DB_PATH = os.path.join(BASE_PATH, constants.ZOOMREC_DB_FILENAME)

FIRMWARE_PATH = os.path.join(BASE_PATH, constants.ARDUINO_FIRMWARE_DIR)
LOG_PATH = os.path.join(BASE_PATH, constants.LOG_DIR)
CONFIG_PATH = os.path.join(BASE_PATH, constants.ARDUINO_CONFIG_DIR)

HTTP_CONTENT_URL_PREFIX = os.getenv('HTTP_CONTENT_URL_PREFIX').rstrip('/')


# Configure basic authentication
app.config['BASIC_AUTH_USERNAME'] = os.getenv('SERVER_USERNAME')
app.config['BASIC_AUTH_PASSWORD'] = os.getenv('SERVER_PASSWORD')
basic_auth = BasicAuth(app)

# Type variable for generic dictionary
DictType = TypeVar('DictType', bound=Dict[str, Any])

def filter_response_fields(
    data: Union[DictType, List[DictType]],
    fields_param: Optional[str],
    required_fields: Optional[Set[str]] = None
) -> Union[DictType, List[DictType]]:
    """
    Filter response data to include only the requested fields.
    
    Args:
        data: The data to filter (can be a dictionary or list of dictionaries)
        fields_param: Comma-separated string of fields to include
        required_fields: Set of fields that should always be included
    
    Returns:
        Filtered data with only the requested and required fields
    """
    if not fields_param:
        return data
    
    # Convert fields_param to a set of requested fields
    requested_fields = set(fields_param.split(',')) if fields_param else set()
    
    # Ensure required fields are always included
    required_fields = required_fields or set()
    included_fields = requested_fields.union(required_fields)
    
    if not included_fields:
        return data
    
    def filter_single_item(item: DictType) -> DictType:
        """Filter a single dictionary to include only the requested fields."""
        return {
            k: v for k, v in item.items() 
            if k in included_fields or not included_fields
        }
    
    # Handle both single item and list responses
    if isinstance(data, list):
        return [filter_single_item(item) for item in data]
    return filter_single_item(data)

# Define the state_changed_callback function
def event_state_changed_callback(old_event, new_event):
    # Timestamp fields to exclude from change detection
    timestamp_fields = [
        EventField.CREATED_TIMESTAMP.value,
        EventField.LAST_UPDATED_TIMESTAMP.value
    ]

    try:
        message = None
        message_users = []
        if old_event is None:
            message = f"Created {Events.nameStr(new_event)}\n"
            message_users.append(users.get(filters=[[UserField.KEY.value, "=", new_event[EventField.USER_KEY.value]]])[0])
        elif new_event is None:
            message = f"Deleted {Events.nameStr(old_event)}\n"
            message_users.append(users.get(filters=[[UserField.KEY.value, "=", old_event[EventField.USER_KEY.value]]])[0])
        else:
            new_user = users.get(filters=[[UserField.KEY.value, "=", new_event[EventField.USER_KEY.value]]])[0]
            message_users.append(new_user)

            changes = []
            # Check for changes in all fields except timestamps
            for field in EventField:
                field_value = field.value
                if field_value not in timestamp_fields and field_value in old_event and field_value in new_event:
                    if old_event[field_value] != new_event[field_value]:
                        # Special handling for user field
                        if field_value == EventField.USER_KEY.value:
                            old_user = users.get(filters=[[UserField.KEY.value, "=", old_event[EventField.USER_KEY.value]]])[0]
                            changes.append(f"user changed from '{old_user[UserField.NAME.value]}' to '{new_user[UserField.NAME.value]}'\n")
                            message_users.append(old_user)
                        # Special handling for status field
                        elif field_value == EventField.STATUS.value:
                            new_status_description = EventStatus.get_description(new_event[field_value])
                            old_status_description = EventStatus.get_description(old_event[field_value])
                            changes.append(f"status changed from '{old_status_description}' to '{new_status_description}'\n")
                        elif field_value == EventField.TYPE.value:  
                            new_type_description = EventType.get_description(new_event[field_value])
                            old_type_description = EventType.get_description(old_event[field_value])
                            changes.append(f"type changed from '{old_type_description}' to '{new_type_description}'\n")
                        else:
                            # Generic handling for other fields
                            # For empty values, replace with "(empty)" for better readability
                            old_value = old_event[field_value] if old_event[field_value] else "(empty)"
                            new_value = new_event[field_value] if new_event[field_value] else "(empty)"
                            changes.append(f"Field: '{field_value}' changed from '{old_value}' to '{new_value}'\n")
            # Build the message
            message = f"Updated {Events.nameStr(new_event)}:\n{', '.join(changes)}"
        
        # Send the message to users
        if message:
            for user in message_users:
                Users.send_message(user, message)
    except Exception as e:
        print(f"Error in event_state_changed_callback: {str(e)}")

# Initialize event storage with the callback
events = SQLLiteEvents(ZOOMREC_DB_PATH, stateChanged=event_state_changed_callback)

# Initialize user manager
users = SQLLiteUser(ZOOMREC_DB_PATH)

# Define the access_state_changed_callback function
def access_state_changed_callback(old_access, new_access):
    """
    Callback function for access state changes.
    
    Args:
        old_access: The previous access state (None for creation)
        new_access: The new access state (None for deletion)
    """
    try:
        access = new_access if new_access is not None else old_access

        # Skip notification if notify_user is disabled
        if access[AccessField.NOTIFY_USER.value] == False:
            app.logger.debug(f"Access notification disabled for {Access.nameStr(access)}")
            return
            
        # Determine action type
        if old_access is None:
            action_type = 'created'
            subject = f"Access created for {access[AccessField.RESOURCE.value]}"
        elif new_access is None:
            action_type = 'deleted'
            subject = f"Access deleted for {access[AccessField.RESOURCE.value]}"
        else:
            action_type = 'updated'
            subject = f"Access updated for {access[AccessField.RESOURCE.value]}"

        # generate plain text body
        plain_body = render_notify_access_template(access, action_type, html=False)
        
        # Generate HTML body
        html_body = render_notify_access_template(access, action_type, html=True)

        # Send notification
        user = users.get(filters=[[UserField.KEY.value, "=", access[AccessField.USER_KEY.value]]])[0] 
        users.notify(
            user,
            plain_body,
            subject,
            html_body,
            additional_emails=access[AccessField.ADDITIONAL_EMAILS.value]
        )
        
    except Exception as e:
        app.logger.error(f"Error in access_state_changed_callback: {str(e)}", exc_info=True)

# Initialize access manager with callback
access_persistence = SQLLiteAccess(ZOOMREC_DB_PATH, stateChanged=access_state_changed_callback)


def render_notify_access_template(access, action_type, html=True):
    """
    Render the access notification template for different actions using Jinja2.
    
    Args:
        access: The access response dictionary
        action_type: The type of action ('created', 'updated', 'deleted')
        html: Whether to render HTML (True) or plain text (False)
        
    Returns:
        Rendered content as string (HTML or plain text)
    """
    try:
        # Choose template based on format
        template_extension = 'html' if html else 'txt'
        template_path = os.path.join(os.path.dirname(__file__), 'res', f'notify_access_template.{template_extension}')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Get the base URL from environment or use a default
        base_url = f"{HTTP_CONTENT_URL_PREFIX}{constants.ROUTE_LIST}"
        resource_url = f"{base_url}/{quote(access[AccessField.ACCESS_KEY.value])}/{quote(access[AccessField.RESOURCE.value])}"
        
        # Format expiration time if present
        expires_at = None
        if AccessField.EXPIRES_AT.value in access and access[AccessField.EXPIRES_AT.value]:
            try:
                from datetime import datetime
                expires_at = datetime.fromisoformat(access[AccessField.EXPIRES_AT.value].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S UTC')
            except:
                expires_at = access[AccessField.EXPIRES_AT.value]
        
        # Set action-specific content
        action_config = {
            'created': {
                'title': '✅ Access Granted',
                'icon': '✅',
                'message': f'You have been granted access to the following resource:'
            },
            'updated': {
                'title': '🔄 Access Updated',
                'icon': '🔄',
                'message': f'Your access to the following resource has been updated:'
            },
            'deleted': {
                'title': '🗑️ Access Revoked',
                'icon': '🗑️',
                'message': f'Your access to the following resource has been revoked:'
            }
        }
        
        config = action_config.get(action_type, action_config['created'])
        
        # Use Jinja2 template rendering
        return render_template_string(
            template_content,
            action_type=action_type,
            action_title=config['title'],
            action_icon=config['icon'],
            action_message=config['message'],
            resource=access[AccessField.RESOURCE.value],
            access_key=access[AccessField.ACCESS_KEY.value],
            access_type=AccessType.get_description(access[AccessField.ACCESS_TYPE.value]),
            resource_url=resource_url,
            expires_at=expires_at
        )
        
    except Exception as e:
        app.logger.error(f"Error rendering access template: {str(e)}")
        # Fallback to simple message
        action_messages = {
            'created': f"Access created for {access[AccessField.RESOURCE.value]}",
            'updated': f"Access updated for {access[AccessField.RESOURCE.value]}",
            'deleted': f"Access deleted for {access[AccessField.RESOURCE.value]}"
        }
        return action_messages.get(action_type, f"Access changed for {access[AccessField.RESOURCE.value]}")

# Create a new user
@app.route(f"{constants.ROUTE_USER}", methods=['POST'])
@basic_auth.required
def create_user():
    try:
        user_data = request.json
        user_data = users.clean(user_data)
        created_user = users.create(user_data)
        return jsonify(created_user), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Retrieve a user by key or all users if no key is provided
# Get all users:
# curl -u myuser:mypassword \
#   "http://localhost:8081/user"
@app.route(f"{constants.ROUTE_USER}", methods=['GET'])
@basic_auth.required
def get_user():
    filters = parse_filter_parameters(request.args)

    try:
        returned_users = users.get(filters=filters)  # Pass the filters to the get method

        if returned_users:
            return jsonify(returned_users), 200 # sucesss, returning content
        else:
            return jsonify({}), 204 # sucsess, but "204 No Content"

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update a user by key
@app.route(f"{constants.ROUTE_USER}/<key>", methods=['PUT'])
@basic_auth.required
def update_user(key):
    try:
        user = request.json
        user[UserField.KEY.value] = key
        users.update(user)
        updated_user = users.get(filters=[[UserField.KEY.value, '=', key]])[0]
        return jsonify(updated_user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete a user by key
@app.route(f"{constants.ROUTE_USER}/<key>", methods=['DELETE'])
@basic_auth.required
def delete_user(key):
    try:
        users.delete(key)
        return jsonify({"message": f"User with key: {key} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Send notification to user
@app.route(f"{constants.ROUTE_USER_NOTIFY}", methods=['POST'])
@basic_auth.required
def notify_user():
    try:
        data = request.get_json()
        user_key = data.get('user_key')
        subject = data.get('subject', constants.DEFAULT_NOTIFICATION_SUBJECT)
        message = data.get('message')
        additional_emails = data.get('additional_emails', [])
        
        if not user_key or not message:
            return jsonify({"error": "user_key and message are required"}), 400

        users_list = users.get(filters=[[UserField.KEY.value, '=', user_key]])
        if not users_list:
            return jsonify({"error": "User not found"}), 404
            
        user = users_list[0]
        users.notify(user, message, subject, additional_emails=additional_emails)
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Error sending notification: {str(e)}")
        return jsonify({"Error sending notification": str(e)}), 500

# Access CRUD endpoints
@app.route(f"{constants.ROUTE_ACCESS}", methods=['POST'])
@basic_auth.required
def create_access():
    try:
        access_request = request.json
        access_request = Access.set_expiry(access_request, access_request.pop(Access.EXPIRE_AFTER_SECONDS, None))
        access_response = access_persistence.create(access_request)
        return jsonify(access_response), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route(f"{constants.ROUTE_ACCESS}", methods=['GET'])
@basic_auth.required
def get_access():
    filters = parse_filter_parameters(request.args)
    try:
        records = access_persistence.get(filters=filters)
        if records:
            return jsonify(records), 200
        else:
            return jsonify(), 204 # sucsess, but "204 No Content"
    except Exception as e:
        app.logger.error(f"Error in get_access: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route(f"{constants.ROUTE_ACCESS}", methods=['DELETE'])
@basic_auth.required
def delete_access():
    try:
        resource = request.args.get('resource')
        access_key = request.args.get('access_key')
        access_type = request.args.get('access_type')
        if not resource or not access_key or not access_type:
            return jsonify({"error": "both resource and access_key parameters are required"}), 400
            
        if access_persistence.delete(resource, access_key, access_type):
            return jsonify({"status": "deleted"}), 200
        else:
            return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route(f"{constants.ROUTE_ACCESS}", methods=['PUT'])
@basic_auth.required
def update_access():
    try:
        access_request = request.json
        access_request = Access.set_expiry(access_request, access_request.pop(Access.EXPIRE_AFTER_SECONDS, None))
        access_response = access_persistence.update(access_request)
        return jsonify(access_response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Validation endpoint (no auth):
@app.route(f"{constants.ROUTE_ACCESS}/validate", methods=['GET'])
def validate_access():
    try:
        resource = request.args.get(AccessField.RESOURCE.value)
        access_key = request.args.get(AccessField.ACCESS_KEY.value)
        access_type = request.args.get(AccessField.ACCESS_TYPE.value)
        
        if not resource or not access_key or not access_type:
            return jsonify({"error": "missing required params: resource, access_key, access_type"}), 400
            
        access = access_persistence.validate_access(resource, access_key, access_type)
        if access:
            # access provided, return access information
            return jsonify(access), 200
        else:
            # no access provided, return empty response
            return jsonify(), 204
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# create event
# curl -u myuser:mypassword \
#   -X POST \
#   -H "Content-Type: application/json" \
#   -d '{
#     "type": "1", 
#     "title": "test", 
#     "dtstart": "18/09/2025 21:45", 
#     "timezone": "Australia/Sydney", 
#     "duration": "30", 
#     "rrule": "FREQ=DAILY;COUNT=2", 
#     "id": "85703777235",
#     "password": "password123",
#     "url": "https://us05web.zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1",
#     "instruction": "record=true",
#     "user": "telegram-chatid=12345678"
#   }' \
#   "http://localhost:8081/event"
@app.route(f"{constants.ROUTE_EVENT}", methods=["POST"])
def create_event():
    try:
        event = request.json
        event = events.create( event)
        return jsonify(event), 200 
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# curl -u myuser:mypassword -X PUT -H "Content-Type: application/json" \
#   -d '{
#         "description": "test",
#         "weekday": "05/05/2024",
#         "time": "15:30", 
#         "timezone": "Australia/Sydney",
#         "duration": "60",
#         "record": "true",
#         "id": "https://us05web.zoom.us/j/83776483885?pwd=xCzmF3kuxu2NbYSckGI28kErQrpXoC.1"
#     }' \
#     "http://localhost:8081/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{constants.ROUTE_EVENT}/<key>", methods=["PUT"])
def update_event(key):
    try:
        event = request.json
        event[EventField.KEY.value] = key
        event = events.update(event)
        return jsonify(event), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# curl -u myuser:mypassword \
#   -X DELETE \
#   "http://localhost:8081/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{constants.ROUTE_EVENT}/<key>", methods=["DELETE"])
@basic_auth.required
def delete_event(key):
    try:
        events.delete(key)
        return jsonify({"message": f"Event with key: {key} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get all events:
# curl -u myuser:mypassword \
#   "http://localhost:8081/event"

# Get event with key:
# curl -u myuser:mypassword \
#   "http://localhost:8081/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{constants.ROUTE_EVENT}", methods=['GET'])
@basic_auth.required
def get_event():
    
    fields_param = request.args.get('fields')

    filters = parse_filter_parameters(request.args)

    try:
        returned_events = events.get(filters=filters)  # Pass the filters to the get method
        
        if returned_events:
            # Filter the response to include only requested fields
            filtered_events = filter_response_fields(
                data=returned_events,
                fields_param=fields_param,
                required_fields={
                    EventField.KEY.value,  # Always include the key field
                    EventField.TITLE.value,  # Always include the title
                    EventField.DTSTART.value,  # Always include the start time
                    EventField.STATUS.value  # Always include the status
                }
            )
            return jsonify(filtered_events), 200  # success, returning content
        else:
            return jsonify({}), 204  # success, but "204 No Content"

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# curl -u myuser:mypassword \
#   "http://localhost:8081/event/next?\
#     client_id=550e8400-e29b-41d4-a716-446655440000&\
#     event_type=1&\
#     lead_time_sec=60&\
#     trail_time_sec=300"
@app.route(f"{constants.ROUTE_EVENT}/{constants.ROUTE_EVENT_NEXT}", methods=['GET'])
@basic_auth.required
def get_event_next():
    try:
        client_id = request.args.get('client_id')
        event_type = request.args.get('event_type')

        if client_id is None:
            return 'mandatory parameter client_id missing', 404
    
        # Retrieve lead_time_sec and trail_time_sec from request parameters
        lead_time_sec = 0
        trail_time_sec = 0
        try:
            lead_time_sec = int(request.args.get('lead_time_sec'))
            trail_time_sec = int(request.args.get('trail_time_sec'))
        except ValueError:
            return 'invalid paramter lead_time_sec and/or trail_time_sec', 404
        except TypeError:
            pass

        response_data = events.get_next(client_id, event_type, lead_time_sec, trail_time_sec)
        # return timestamp in ISO 8601 format 
        if not response_data is None:
            response_data['dtstart_instance'] = response_data['dtstart_instance'].isoformat()
            response_data['dtend_instance'] = response_data['dtend_instance'].isoformat()
            response_data['dtstart_instance_lead'] = response_data['dtstart_instance_lead'].isoformat()
            response_data['dtend_instance_trail'] = response_data['dtend_instance_trail'].isoformat()
            response_data['dtnow'] = response_data['dtnow'].isoformat()
            return jsonify(response_data), 200
        else:
            return jsonify({}), 204 # sucsess, but "204 No Content"
    except Exception as e:
        app.logger.error(f"Error getting next event: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# curl -X POST http://localhost:8081/log \
#     -H "Content-Type: application/json" \
#     -u myuser:mypassword \
#     -d '{"id":"ESP8266Zoomrec","content":"2025-06-01 14:29:12 DEBUG Entering deep sleep for 60 seconds..."}'
@app.route(f"{constants.ROUTE_LOG}", methods=['POST'])
@basic_auth.required
def log_handler():
    data = request.json
    log_id = data.get(EventField.ID.value)
    log_content = data.get('content')
    if log_content:
        log_content = unquote(log_content)

    if log_id is None or log_content is None:
        return jsonify({'error': 'id and content are required'}), 400

    log_filename = os.path.join(LOG_PATH, f"{log_id}_log.txt")

    try:
        # Check if the log file exists  
        if os.path.exists(log_filename):
            mode = 'a'
        else:
            mode = 'w'

        # Open the log file in the determined mode
        with open(log_filename, mode) as log_file:
            log_file.write(log_content)

    except Exception as e:  
        return jsonify({'error': str(e)}), 500

    return jsonify({'message': 'Log appended successfully'}), 200

# curl -H "x-ESP8266-version: ESP8266_zoomrec.ino-May  7 2023-15:26:18" \
#   -u myuser:mypassword \
#   --output firmware.ino.bin \
#   http://localhost:8081/firmware
@app.route(f"{constants.ROUTE_FIRMWARE}", methods=['GET'])
@basic_auth.required
def get_firmware():
    """
    Handle firmware update requests from Arduino devices.
    
    The device sends its current firmware version in the x-ESP8266-version header.
    The server will return a newer firmware if available, or a 304 Not Modified response
    if the device already has the latest version.
    """
    try:
        firmware_version = request.headers.get('x-ESP8266-version')
        if not firmware_version:
            app.logger.error(f"{request.endpoint}: No firmware version specified in request headers")
            return jsonify({"message": "Firmware version not specified"}), 400
        
        app.logger.debug(f"{request.endpoint}: Firmware update requested for {firmware_version}")

        try:
            # Parse the firmware name and version from the header
            firmware_name, firmware_version_time = parse_version_string(firmware_version)
        except ValueError as e:
            return jsonify({"message": "Invalid firmware version format"}), 400
                    
        # Find the most recent compatible firmware that's newer than the current version
        firmware_file, error_dict = find_compatible_firmware(
            FIRMWARE_PATH, 
            firmware_name, 
            firmware_version_time
        )
        
        if not firmware_file and error_dict is not None:
            error_code = error_dict.get('error_code')
            error_msg = error_dict.get('error_msg', 'Unknown error')

            # Map error codes to appropriate HTTP status codes
            status_codes = {
                ERROR_NO_COMPATIBLE_FIRMWARE: 304,  # Not Modified
                ERROR_FIRMWARE_DIR_NOT_FOUND: 500,
                ERROR_INVALID_FIRMWARE_VERSION:500,
                ERROR_UNEXPECTED: 500
            }

            status_code = status_codes.get(error_code, 500)
            app.logger.debug(error_msg)
            return jsonify({"message": error_msg}), status_code
        else:  
            # Send the firmware file
            return send_file(
                firmware_file[0] if isinstance(firmware_file, tuple) else firmware_file,
                as_attachment=True,
                mimetype='application/octet-stream',
                download_name=os.path.basename(firmware_file[0] if isinstance(firmware_file, tuple) else firmware_file)
            )
    except Exception as e:
        message = "Error processing firmware update request"
        app.logger.error(f"{request.endpoint}: {message}: {str(e)}", exc_info=True)
        return jsonify({"message": message}), 500
    
# curl -v \
#   -H "x-ESP8266-version: ESP8266_zoomrec.ino-May  7 2024-15:26:20" \
#   -H "x-ESP8266-config-version: ESP8266_zoomrec.ino-May  7 2024-15:26:20" \
#   -u myuser:mypassword \
#   "http://localhost:8081/config"
@app.route(f"{constants.ROUTE_CONFIG}", methods=['GET'])
@basic_auth.required
def get_config():
    """
    Serve the configuration file.
    Headers:
        x-ESP8266-version: config_name-{date} (required)
        x-ESP8266-config-version: config-{date} (required) - Current config version on device
    """
    try:
        # Get the firmware version from the header
        firmware_header = request.headers.get('x-ESP8266-version')
        if not firmware_header:
            app.logger.error(f"{request.endpoint}: Missing x-ESP8266-version header")
            return jsonify({"message": "Missing x-ESP8266-version header"}), 400
            
        # Get the current config version from the device
        config_header = request.headers.get('x-ESP8266-config-version')
        if not config_header:
            app.logger.error(f"{request.endpoint}: Missing x-ESP8266-config-version header")
            return jsonify({"message": "Missing x-ESP8266-config-version header"}), 400

        app.logger.debug(f"{request.endpoint}: Config update requested for firmware version '{firmware_header}' with config version '{config_header}'")
        
        try:
            # Parse the firmware version (format: name-{date})
            firmware_name, firmware_version = parse_version_string(firmware_header)
        except ValueError:
            return jsonify({"message": "Invalid firmware version format"}), 400

        try:
            # Parse the current config version (format: name-{date})
            _, current_config_version = parse_version_string(config_header)
        except ValueError as e:
            return jsonify({"message": "Invalid config version format"}), 400

        # Get the config file path, ensuring it's compatible with the firmware and newer than current config
        filepath, error_dict = get_config_file_path(
            CONFIG_PATH,
            firmware_name,
            firmware_version,
            current_config_version
        )
        
        if not filepath and error_dict is not None:
            error_code = error_dict.get('error_code', 'unknown_error')
            error_msg = error_dict.get('error_msg', 'An unknown error occurred')
            
            # Map error codes to appropriate HTTP status codes
            status_codes = {
                ERROR_NO_NEWER_CONFIG: 304,  # Not Modified
                ERROR_CONFIG_DIR_NOT_FOUND: 500,
                ERROR_CONFIG_DIR_READ: 500,
                ERROR_NO_COMPATIBLE_CONFIG: 204,
                ERROR_NO_CONFIG_FILES: 204,
                ERROR_NO_VALID_CONFIG_FILES: 204,
                ERROR_CONFIG_READ: 500,
                ERROR_UNEXPECTED: 500
            }
            
            status_code = status_codes.get(error_code, 500)
            app.logger.debug(error_msg)
            return jsonify({"message": error_msg}), status_code
        else:
            # Send the config file
            with open(filepath, 'r') as f:
                config_data = json.load(f)
                return jsonify(config_data), 200     

    except Exception as e:
        error_msg = f"Error serving config file: {str(e)}"
        app.logger.error(f"{request.endpoint}: {error_msg}", exc_info=True)
        return jsonify({"message": "Error serving config file"}), 500

# http based file access

def get_file_access(access_key: str, resource: str) -> str:
    """
    Validate access and return the full file path if authorized.
    
    Args:
        access_key: The access key for the resource
        resource: The resource identifier (without path or extension)
        
    Returns:
        str: Full path to the file if access is authorized
        
    Raises:
        PermissionError: If access is not authorized
        FileNotFoundError: If user or resource is not found
    """
    try:
        # First validate the access with HTTP_SERVER_ACCESS type
        (basename, file_ext) = os.path.splitext(resource)
        # for validating access we only check everything before first .
        if '.' in basename:
            resource_validate = basename.split('.')[0]
        else:
            resource_validate = basename
        access_granted = access_persistence.validate_access( resource_validate, access_key, AccessType.HTTP_SERVER_ACCESS.value)
        if not access_granted:
            raise PermissionError("unauthorized")
        
        user_key = access_granted[AccessField.USER_KEY.value]
        user = users.get(filters=[[UserField.KEY.value, '=', user_key]])[0]
        if not user:
            app.logger.error(f"User not found for user_key: {user_key}")
            raise FileNotFoundError("user not found")

        sftp_username = user.get(UserField.SFTP_USERNAME.value)
        if not sftp_username:
            raise FileNotFoundError("sftp_username not found for user")

        file_dir = os.path.join(BASE_PATH, constants.SFTP_DATA_MOUNT_PATH, sftp_username, constants.SFTP_RECORDINGS_DIR)
        return os.path.join(file_dir, basename + file_ext)
    except Exception as e:
        app.logger.error(f"Error in get_file_access: {str(e)}", exc_info=True)
        if isinstance(e, (PermissionError, FileNotFoundError)):
            raise
        raise Exception("error accessing file")

def _range_response(path, mimetype='video/mp4'):
    """Generate a response with support for HTTP Range requests for H.265 video.
    
    Args:
        path: Path to the video file
        mimetype: MIME type of the video file
        
    Returns:
        Flask Response object with appropriate headers
    """
    try:
        # Convert to absolute path to avoid any path resolution issues
        abs_path = os.path.abspath(path)
        app.logger.debug(f"Absolute file path: {abs_path}")
        
        file_size = os.path.getsize(abs_path)
        app.logger.debug(f"File size: {file_size} bytes")
        
        range_header = request.headers.get('Range', '')
        app.logger.debug(f"Range header: {range_header}")
        
        # Set default headers for all responses
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Type': mimetype,
            'Content-Length': str(file_size),
            'X-Content-Type-Options': 'nosniff',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Video-Codec': 'hevc',
            'X-Content-Duration': str(file_size)
        }
        
        # If no range header, return the full file with 200 OK
        if not range_header:
            app.logger.debug("No range header, sending full file")
            return send_file(
                path,
                mimetype=mimetype,
                conditional=True,
                download_name=os.path.basename(path),
                etag=True,
                last_modified=os.path.getmtime(path),
                max_age=0
            )
        
        # Parse the range header (e.g., 'bytes=0-999')
        if '=' not in range_header:
            raise ValueError("Invalid range header format")
            
        range_type, range_spec = range_header.split('=', 1)
        if range_type.strip().lower() != 'bytes':
            app.logger.error(f"Invalid range type: {range_type}")
            return Response('Invalid range type', status=400, headers=headers)
        
        # Handle single range (we don't support multiple ranges)
        range_parts = range_spec.strip().split('-')
        if len(range_parts) != 2:
            app.logger.error(f"Invalid range format: {range_spec}")
            return Response('Invalid range format', status=400, headers=headers)
            
        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1
        
        # Handle suffix-byte-range-spec (e.g., 'bytes=-500' for last 500 bytes)
        if not range_parts[0] and range_parts[1]:
            end = file_size - 1
            start = max(0, end - int(range_parts[1]) + 1)
        
        # Ensure end is within bounds
        end = min(end, file_size - 1)
        
        # Validate range
        if start >= file_size or end >= file_size or start > end or start < 0:
            app.logger.error(f"Invalid range: {start}-{end} for file size {file_size}")
            headers['Content-Range'] = f'bytes */{file_size}'
            return Response('Range Not Satisfiable', status=416, headers=headers)
            
        # Calculate content length
        content_length = end - start + 1
        
        app.logger.debug(f"Serving range: {start}-{end} (size: {content_length})")
        
        # Create a partial response
        def generate():
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 8192  # 8KB chunks
                
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        # Update headers for partial content
        headers.update({
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(content_length),
            'Content-Disposition': f'inline; filename="{os.path.basename(path)}"'
        })
        
        response = Response(
            generate(),
            status=206,  # Partial Content
            headers=headers,
            direct_passthrough=True
        )
        
        # Set appropriate caching headers for streaming
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
        response.expires = 0
        
        return response
        
    except ValueError as e:
        app.logger.error(f"Error parsing range header: {str(e)}", exc_info=True)
        return Response('Invalid range header', status=400, headers=headers)
    except Exception as e:
        app.logger.error(f"Error serving range request: {str(e)}", exc_info=True)
        return Response('Internal Server Error', status=500, headers=headers)

# List files for a resource
@app.route(f"{constants.ROUTE_LIST}/<access_key>/<path:resource>")
def list_files(access_key, resource):
    """
    List all files for a resource that the access key has access to.
    
    Args:
        access_key: The access key for the resource
        resource: The resource identifier (without path or extension)
        
    Returns:
        HTML page with links to all accessible files
    """
    try:
        # Validate access and get the base path
        try:
            # Get the base directory from the first matching file
            base_path = get_file_access(access_key, resource)
            base_dir = os.path.dirname(base_path)
            resource_base = os.path.basename(resource)
            
            # Find all files starting with the resource base name
            pattern = os.path.join(base_dir, f"{resource_base}*")
            matching_files = glob.glob(pattern)
            
            # Process files
            files = []
            for file_path in matching_files:
                if os.path.isfile(file_path):
                    file_name = os.path.basename(file_path)
                    file_url = f"{HTTP_CONTENT_URL_PREFIX}{constants.ROUTE_FILE}/{quote(access_key)}/{quote(file_name)}"
                    file_stat = os.stat(file_path)
                    files.append({
                        'name': file_name,
                        'url': file_url,
                        'size': file_stat.st_size,
                        'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            # Sort files by name
            files.sort(key=lambda x: x['name'])
            
            # Get template directory
            template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'res')
            template_path = os.path.join(template_dir, 'list_template.html')
            
            # Read and render template
            with open(template_path, 'r') as f:
                template = f.read()
            
            return render_template_string(
                template,
                files=files,
                resource=resource,
                filesizeformat=lambda x: f"{x/1024/1024:.1f} MB" if x > 1024*1024 else f"{x/1024:.1f} KB"
            )
            
        except (PermissionError, FileNotFoundError) as e:
            app.logger.warning(f"Access denied or file not found: {str(e)}")
            return "Access denied or resource not found", 404
            
    except Exception as e:
        app.logger.error(f"Error listing files: {str(e)}")
        return "An error occurred while processing your request", 500

# http access to return resource files
@app.route(f"{constants.ROUTE_FILE}/<string:access_key>/<path:resource>", methods=['GET'])
def get_file(access_key: str, resource: str):
    """
    Serve a file with proper MIME type based on file extension.
    The resource should be provided without extension in the URL.
    """
    try:
        # Get the full file path with access validation
        file_path = get_file_access(access_key, resource)
        
        # Get MIME type based on file extension
        (basename, file_ext) = os.path.splitext(resource)
        mime_type, _ = mimetypes.guess_type('file' + file_ext)
        if not mime_type:
            mime_type = 'application/octet-stream'  # Default MIME type if unknown
        
        # Check if this is a range request (for video/audio)
        range_header = request.headers.get('Range', None)
        if range_header and any(mime_type.startswith(t) for t in ['video/', 'audio/']):
            return _range_response(file_path, mime_type)
            
        # For non-range requests, use send_file which handles most file types well
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=basename + file_ext
        )
        
    except PermissionError as e:
        app.logger.error(f"Permission denied: {str(e)}")
        abort(403, description="Access denied")
    except FileNotFoundError as e:
        app.logger.error(f"File not found: {str(e)}")
        abort(404, description="File not found")
    except Exception as e:
        app.logger.error(f"Error serving file: {str(e)}")
        abort(500, description="Internal server error")

# @app.route("/view/<path:access_key>/<resource>", methods=['GET'])
# def view_video(access_key, resource):
#     try:
#         try:
#             video_file = get_file_access(access_key, resource)
#         except PermissionError as e:
#             app.logger.error(f"Permission Error in view_video: {str(e)}")
#             return jsonify({"error": "access denied"}), 403
#         except FileNotFoundError as e:
#             app.logger.error(f"File Not Found Error in view_video: {str(e)}")
#             return jsonify({"error": "video not found"}), 404
        
#         # Check if file exists
#         if not os.path.exists(video_file):
#             app.logger.error(f"Video file not found: {video_file}")
#             return jsonify({"error": "video not found"}), 404
            
#         # If we get here, the file exists and is accessible
#         seconds = request.args.get('seconds', default=None, type=float)
#         seconds_js = str(seconds) if seconds is not None else "null"
#         stream_url = f"/stream/{access_key}/{resource}"
        
#         # Load and render the template
#         template_path = os.path.join(os.path.dirname(__file__), 'res', 'view.html')
#         try:
#             with open(template_path, 'r', encoding='utf-8') as f:
#                 html = f.read()
            
#             html = html.replace('{{resource}}', resource)
#             html = html.replace('{{stream_url}}', stream_url)
#             html = html.replace('{{seconds_js}}', seconds_js)
#             return Response(html, mimetype='text/html')
            
#         except FileNotFoundError:
#             app.logger.error(f"Template file not found: {template_path}")
#             return jsonify({"error": "internal server error"}), 500
            
#     except Exception as e:
#         app.logger.error(f"Error in view_video: {str(e)}")
#         return jsonify({"error": "internal server error"}), 500

# @app.route("/stream/<path:access_key>/<resource>", methods=['GET'])
# def stream_video(access_key, resource):
#     try:
#         app.logger.debug(f"Stream request - Resource: {resource}")
        
#         try:
#             video_file = get_file_access(access_key, resource)
#         except PermissionError as e:
#             app.logger.error(f"Permission Error in stream_video: {str(e)}")
#             return jsonify({"error": "access denied"}), 403
#         except FileNotFoundError as e:
#             app.logger.error(f"File Not Found Error in stream_video: {str(e)}")
#             return jsonify({"error": "video not found"}), 404
            
#         app.logger.debug(f"Video file path: {video_file}")
        
#         if not os.path.exists(video_file):
#             app.logger.error(f"Video file not found: {video_file}")
#             return jsonify({"error": "video not found"}), 404
            
#         # Get file stats for logging
#         file_size = os.path.getsize(video_file)
#         app.logger.debug(f"Video file size: {file_size} bytes")
        
#         # Set MIME type for H.265 video in MP4 container
#         mime_type = 'video/mp4; codecs=hevc'
        
#         # Process the range request
#         response = _range_response(video_file, mime_type)
        
#         # Add CORS and other headers
#         response.headers.update({
#             'Access-Control-Allow-Origin': '*',
#             'Access-Control-Allow-Headers': 'Range',
#             'Access-Control-Expose-Headers': 'Content-Range, Content-Length, Accept-Ranges',
#             'Content-Type': mime_type,
#             'Accept-Ranges': 'bytes',
#             'Content-Disposition': f'inline; filename="{resource}.{constants.VIDEO_EXTENSION}"',
#             'Cache-Control': 'no-cache',
#             'X-Content-Type-Options': 'nosniff',
#             'X-Video-Codec': 'hevc',
#             'X-Content-Duration': str(file_size)  # For debugging
#         })
        
#         return response
            
#     except Exception as e:
#         app.logger.error(f"Unexpected error in stream_video: {str(e)}", exc_info=True)
#         return jsonify({"error": "internal server error"}), 500
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize MIME types
    mimetypes.init()
    # Add any custom MIME types if needed
    # mimetypes.add_type('application/wasm', '.wasm')
    
    app.run(debug=True, host='0.0.0.0', port=os.getenv("SERVER_PORT"))