from flask import Flask, request, jsonify, send_file
from flask_basicauth import BasicAuth
from datetime import datetime, timezone
import os.path
from typing import Any, Dict, List, Optional, Set, TypeVar, Union
from shared.events import Events, EventStatus, EventField, SQLLiteEvents, EventType
from urllib.parse import unquote
from shared.users import SQLLiteUser, Users, UserField
import logging
import json
from shared import constants
from shared.utilities import start_debug
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
    # When running with Gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    if gunicorn_logger.handlers:
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)
else:
    # When running standalone
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    app.logger = logging.getLogger(__name__)

BASE_PATH = os.getenv('ZOOMREC_HOME')
ZOOMREC_DB_PATH = os.path.join(BASE_PATH, constants.ZOOMREC_DB_FILENAME)

FIRMWARE_PATH = os.path.join(BASE_PATH, constants.ARDUINO_FIRMWARE_DIR)
LOG_PATH = os.path.join(BASE_PATH, constants.LOG_DIR)
CONFIG_PATH = os.path.join(BASE_PATH, constants.ARDUINO_CONFIG_DIR)

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
    filters = []

    # Retrieve filter parameters from the request
    for key, value in request.args.items():
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
        return jsonify({"message": "User with key: {key} deleted successfully"}), 200
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
    filters = []
    fields_param = request.args.get('fields')

    # Retrieve filter parameters from the request
    for key, value in request.args.items():
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

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=os.getenv("SERVER_PORT"))