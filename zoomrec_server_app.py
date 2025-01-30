from flask import Flask, request, Response, jsonify, send_file # pip install flask
from flask_basicauth import BasicAuth # pip install flask-basicauth
from datetime import datetime
import os.path
import yaml
from events import FIELDNAMES, Events, EventStatus, EventField, SQLLiteEvents
from urllib.parse import unquote
from users import SQLLiteUser, Users, UserField

app = Flask(__name__)

BASE_PATH = os.getenv('HOME')
ZOOMREC_DB = 'zoomrec_server_db'
ZOOMREC_DB_PATH = os.path.join(BASE_PATH, ZOOMREC_DB)

# Load configuration from YAML file
with open('zoomrec_server_app.yaml', "r") as f:
    config = yaml.safe_load(f)

FIRMWARE_PATH = os.path.join(BASE_PATH, os.getenv('FIRMWARE_SUBDIR'))
LOG_PATH = os.path.join(BASE_PATH, os.getenv('LOG_SUBDIR'))

# Configure basic authentication
app.config['BASIC_AUTH_USERNAME'] = os.getenv('SERVER_USERNAME')
app.config['BASIC_AUTH_PASSWORD'] = os.getenv('SERVER_PASSWORD')
basic_auth = BasicAuth(app)

# Define the state_changed_callback function
def event_state_changed_callback(old_event, new_event):
    try:
        message = None
        if old_event is None:
            event = new_event
            message = f"Create new event with title '{new_event[EventField.TITLE.value]}' and key '{new_event[EventField.KEy.value]}'."
        elif new_event is None:
            event = old_event
            message = f"Deleted event with title '{new_event[EventField.TITLE.value]}' and key '{new_event[EventField.KEy.value]}'."
        else:
            event = new_event
            if old_event[EventField.STATUS.value] != new_event[EventField.STATUS.value]:
                new_status_description = EventStatus.get_description(new_event[EventField.STATUS.value])
                old_status_description = EventStatus.get_description(old_event[EventField.STATUS.value])
                message = f"Event '{new_event[EventField.TITLE.value]}' status changed from {old_status_description} to {new_status_description}"
        
            if message:
                user = users.get(event.get(EventField.USER_KEY.value))
                if user:
                    Users.send_message(user, message)
    except Exception as e:
        print(f"Error in event_state_changed_callback: {str(e)}")

# Initialize event storage with the callback
# events = CSVEvents(CSV_PATH, delimiter=';', stateChanged=state_changed_callback)
events = SQLLiteEvents(ZOOMREC_DB_PATH, stateChanged=event_state_changed_callback)

# Initialize user manager
users = SQLLiteUser(ZOOMREC_DB_PATH)

# Create a new user
@app.route(f"{config['ROUTE_USER']}", methods=['POST'])
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
# get all users: curl -u myuser:mypassword "http://localhost:8081/user"
# get with key: curl -u myuser:mypassword "http://localhost:8081/user/SXThWeEpL3aiEWJ6tbytMA"
# get by login: curl -u myuser:mypassword "http://localhost:8081/user?login=johndoe"

@app.route(f"{config['ROUTE_USER']}/<user_key>", methods=['GET'])
@app.route(config['ROUTE_USER'], methods=['GET'])
@basic_auth.required
def get_user(user_key=None):
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
        if user_key:
            user = users.get(user_key=user_key)
        else:
            all_users = users.get(filters=filters)  # Pass the filters to the get method
            return jsonify(all_users), 200

        if user:
            return jsonify(user), 200
        else:
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update a user by key
@app.route(f"{config['ROUTE_USER']}/<key>", methods=['PUT'])
@basic_auth.required
def update_user(key):
    try:
        user = request.json
        user[UserField.KEY.value] = key
        users.update(user)
        updated_user = users.get(key)[0]
        return jsonify(updated_user), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete a user by key
@app.route(f"{config['ROUTE_USER']}/<key>", methods=['DELETE'])
@basic_auth.required
def delete_user(key):
    try:
        users.delete(key)
        return jsonify({"message": "User with key: {key} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# create event
# curl -u myuser:mypassword \
#      -X POST \
#      -H "Content-Type: application/json" \
#      -d '{
#            "type": "1", 
#            "title": "test", 
#            "dtstart": "18/09/2025 21:45", 
#            "timezone": "Australia/Sydney", 
#            "duration": "30", 
#            "rrule": "FREQ=DAILY;COUNT=2", 
#            "id": "85703777235",
#            "password": "password123",
#            "url": "https://us05web.zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1",
#            "instruction": "record=true",
#            "user": "telegram-chatid=12345678"
#          }' \
#      "http://localhost:8081/event"
@app.route(f"{config['ROUTE_EVENT']}", methods=["POST"])
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
@app.route(f"{config['ROUTE_EVENT']}/<key>", methods=["PUT"])
def update_event(key):
    try:
        event = request.json
        event[EventField.KEY.value] = key
        event = events.update(event)
        return jsonify(event), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# curl -u myuser:mypassword -X DELETE "http://localhost:8081/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{config['ROUTE_EVENT']}/<key>", methods=["DELETE"])
@basic_auth.required
def delete_event(key):
    try:
        events.delete(key)
        return jsonify({"message": f"Event with key: {key} deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# all events: curl -u myuser:mypassword "http://localhost:8080/event"
# with key: curl -u myuser:mypassword "http://localhost:8080/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{config['ROUTE_EVENT']}/<event_key>", methods=['GET'])
@app.route(config['ROUTE_EVENT'], methods=['GET'])
@basic_auth.required
def get_event(event_key=None):
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
        if event_key:
            event = events.get(event_key=event_key)
        else:
            all_event = events.get(filters=filters)  # Pass the filters to the get method
            return jsonify(all_event), 200

        if event:
            return jsonify(event), 200
        else:
            return jsonify({"error": "No Events found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# curl -u myuser:mypassword "http://localhost:8080/event/next?astimezone=Australia/Sydney&leadinsecs=60&leadoutsecs=60"
@app.route(f"{config['ROUTE_EVENT']}/{config['ROUTE_EVENT_NEXT']}", methods=['GET'])
@basic_auth.required
def get_event_next():
    # Retrieve leadInSecs and leadOutSecs from request parameters
    leadInSecs = 0
    leadOutSecs = 0
    try:
        leadInSecs = int(request.args.get('leadinsecs'))
        leadOutSecs = int(request.args.get('leadoutsecs'))
    except ValueError:
        return 'invalid paramter leadinsecs and/or leadoutsecs', 404
    except TypeError:
        pass

    astimezone = request.args.get('astimezone')
    if events.is_valid_timezone(astimezone):
        response_data = events.find_next(events.read(), astimezone, leadInSecs, leadOutSecs)
        # return timestamp in ISO 8601 format 
        if not response_data is None:
            response_data['start'] = response_data['start'].isoformat()
            response_data['end'] = response_data['end'].isoformat()
            response_data['start_astimezone'] = response_data['start_astimezone'].isoformat()
            response_data['end_astimezone'] = response_data['end_astimezone'].isoformat()
        return jsonify(response_data)
    else:
        return 'invalid paramter timezone ', 404

def get_file_mtime(file_path):
    mtime = os.path.getmtime(file_path)
    timestamp = datetime.fromtimestamp(mtime)
    timestamp = timestamp.replace(microsecond=0)
    return timestamp

def parse_version(version_string):
    parts = version_string.split('-')
    if len(parts) != 3:
        raise ValueError('Invalid version string')
    filename, date_str, time_str = parts
    date_time_str = f"{date_str.strip()} {time_str.strip()}"
    try:
        timestamp = datetime.strptime(date_time_str, '%b %d %Y %H:%M:%S')
        timestamp = timestamp.replace(microsecond=0)
    except ValueError:
        raise ValueError('Invalid version string')
    return filename, timestamp

# curl -H "x-ESP8266-version: ESP8266_Template.ino-May  7 2023-15:26:18" -u myuser:mypassword --output firmware.ino.bin http://localhost:8080/firmware
@app.route(config['ROUTE_FIRMWARE'], methods=['GET'])
@basic_auth.required
def get_firmware():
    firmware_version = request.headers.get('x-ESP8266-version')
    if not firmware_version:
        return 'Firmware version not specified', 400
    try:
        filename, firmware_version_mtime = parse_version(firmware_version)
    except ValueError:
        return 'Invalid firmware version', 400
    filepath = os.path.join( FIRMWARE_PATH, filename + '.bin')
    if not os.path.isfile(filepath):
        return 'Firmware not found', 404
    firmware_file_mtime = get_file_mtime(filepath)
    # difference needs to be min 60s as there are some small time differences
    if (firmware_file_mtime - firmware_version_mtime).total_seconds() >= 60:
        return send_file(filepath, as_attachment=True, mimetype='application/octet-stream')
    else:
        return '', 304  # Not Modified
    
# curl -X POST -H "Content-Type: application/json" -u admin:myadminpw -d @log_entry.json http://localhost:8080/log
@app.route('/log', methods=['POST'])
@basic_auth.required
def log_handler():
    data = request.json
    log_id = data.get(EventField.ID.value)
    log_content = data.get('content')
    if log_content:
        log_content = unquote(log_content)

    if log_id is None or log_content is None:
        return jsonify({'error': 'id and content are required'}), 400

    log_filename = f'{LOG_PATH}{log_id}.log'

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
     
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=os.getenv("DOCKER_API_PORT", "8080"))