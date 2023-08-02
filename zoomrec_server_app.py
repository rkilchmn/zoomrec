from flask import Flask, request, Response, jsonify, send_file # pip install flask
from flask_basicauth import BasicAuth # pip install flask-basicauth
# import csv
from datetime import datetime
import os.path
import yaml
# import sys
from events import read_events_from_csv, find_next_event, is_valid_timezone
# from io import StringIO

app = Flask(__name__)

BASE_PATH = os.getenv('HOME')
CSV_PATH = os.path.join(BASE_PATH, "meetings.csv")

# Load configuration from YAML file
with open( 'zoomrec_server.yaml', "r") as f:
    config = yaml.safe_load(f)

FIRMWARE_PATH = os.path.join(BASE_PATH, os.getenv('FIRMWARE_SUBDIR'))

# Configure basic authentication
app.config['BASIC_AUTH_USERNAME'] = os.getenv('SERVER_USERNAME')
app.config['BASIC_AUTH_PASSWORD'] = os.getenv('SERVER_PASSWORD')
basic_auth = BasicAuth(app)

# curl -u myuser:mypassword "http://localhost:8080/event?last_change=2023-05-10T12:00:00"
@app.route(config['ROUTE_EVENT'], methods=['GET'])
@basic_auth.required
def get_event():
    last_change = request.args.get('last_change')
    file_timestamp = datetime.fromtimestamp(os.path.getmtime((CSV_PATH)))

    if last_change:
        last_change_timestamp = datetime.fromisoformat((last_change))
        if file_timestamp <= last_change_timestamp:
            return jsonify([])  # Return an empty list if file timestamp is not later than last_change

    events = read_events_from_csv(CSV_PATH)
    return jsonify(events)

# curl -u myuser:mypassword http://localhost:8080/event/next?astimezone=Australia/Sydney
@app.route(config['ROUTE_EVENT_NEXT'], methods=['GET'])
@basic_auth.required
def get_event_next():
    astimezone = request.args.get('astimezone')
    if is_valid_timezone(astimezone):
        response_data = find_next_event( read_events_from_csv(CSV_PATH), astimezone)
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
    
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=os.getenv("DOCKER_API_PORT", "8080"))


