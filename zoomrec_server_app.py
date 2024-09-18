from flask import Flask, request, Response, jsonify, send_file # pip install flask
from flask_basicauth import BasicAuth # pip install flask-basicauth
from datetime import datetime
import os.path
import yaml
from events import FIELDNAMES, EventField, CSVEvents
from urllib.parse import unquote

app = Flask(__name__)

BASE_PATH = os.getenv('ZOOMREC_HOME')
CSV_PATH = os.path.join(BASE_PATH, os.getenv('FILENAME_MEETINGS_CSV'))

# Load configuration from YAML file
with open('zoomrec_server.yaml', "r") as f:
    config = yaml.safe_load(f)

FIRMWARE_PATH = os.path.join(BASE_PATH, os.getenv('FIRMWARE_SUBDIR'))
LOG_PATH = os.path.join(BASE_PATH, os.getenv('LOG_SUBDIR'))

# Configure basic authentication
app.config['BASIC_AUTH_USERNAME'] = os.getenv('SERVER_USERNAME')
app.config['BASIC_AUTH_PASSWORD'] = os.getenv('SERVER_PASSWORD')
basic_auth = BasicAuth(app)

# Initialize event storage
events = CSVEvents(CSV_PATH, delimiter=';')

# create event
# curl -u myuser:mypassword \
#      -X POST \
#      -H "Content-Type: application/json" \
#      -d '{
#            "description": "test", 
#            "weekday": "18/09/2024", 
#            "time": "13:30", 
#            "timezone": "Australia/Sydney", 
#            "duration": "30", 
#            "record": "true", 
#            "id": "https://us05web.zoom.us/j/84548756066?pwd=35dp6HKKTU60LLOlShON9Kb8bMnNb4.1"
#          }' \
#      "http://localhost:8081/event"

# curl -u myuser:mypassword -X POST -H "Content-Type: application/json" -d '{"description": "test", "weekday": "05/05/2024", "time": "14:30", "timezone":"Australia/Sydney", "duration": "60", "record": "true", "id": "https://us05web.zoom.us/j/83776483885?pwd=xCzmF3kuxu2NbYSckGI28kErQrpXoC.1"}' "http://localhost:8081/event"
@app.route(f"{config['ROUTE_EVENT']}", methods=["POST"])
def create_event():
    try:
        event = {}
        for fieldname in FIELDNAMES:
            if fieldname in request.json:
                event[fieldname] = request.json[fieldname]
        event = events.validate(event)
        event[EventField.KEY.value] = events.generate_unique_id()
        all_events = events.read()
        all_events = events.remove_past(all_events, 300)
        all_events.append(event)
        events.write(all_events)
        return jsonify(event) # return created event including 'key' in order to modify
    except Exception as e:
        return jsonify({"error": str(e)}), 404

# curl -u myuser:mypassword -X PUT -H "Content-Type: application/json" -d '{"description": "test", "weekday": "05/05/2024", "time": "15:30", "timezone":"Australia/Sydney", "duration": "60", "record": "true", "id": "https://us05web.zoom.us/j/83776483885?pwd=xCzmF3kuxu2NbYSckGI28kErQrpXoC.1"}' "http://localhost:8081/event/G4JbZYQN65Ba35jfbyiHsj"
@app.route(f"{config['ROUTE_EVENT']}/<key>", methods=["PUT"])
def update_event(key):
    try:
        all_events = events.read()
        for i, e in enumerate(all_events):
            if e[EventField.KEY.value] == key:
                for fieldname in FIELDNAMES:
                    if fieldname in request.json:
                        all_events[i][fieldname] = request.json[fieldname]
                all_events[i] = events.validate(all_events[i])
                events.write(all_events)
                return jsonify(all_events[i]) # return updated event
        return jsonify({"error": "Event not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 404

# curl -u myuser:mypassword "http://localhost:8080/event?last_change=2023-05-10T12:00:00"
@app.route(f"{config['ROUTE_EVENT']}/<key>", methods=['GET'])
@app.route(config['ROUTE_EVENT'], methods=['GET'])
@basic_auth.required
def get_event(key=None):
    last_change = request.args.get('last_change')
    file_timestamp = datetime.fromtimestamp(os.path.getmtime(CSV_PATH))

    if last_change:
        last_change_timestamp = datetime.fromisoformat(last_change)
        if file_timestamp <= last_change_timestamp:
            return jsonify([])  # Return an empty list if file timestamp is not later than last_change

    all_events = events.read()

    if key:
        event = next((e for e in all_events if e[EventField.KEY.value] == key), None)
        if event:
            return jsonify(event)
        else:
            return jsonify({"error": "Event not found"}), 404

    return jsonify(all_events)

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