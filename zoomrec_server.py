from flask import Flask, request, Response, jsonify, send_file # pip install flask
from flask_basicauth import BasicAuth # pip install flask-basicauth
import csv
import datetime
import os.path
import yaml
import sys
from io import StringIO

app = Flask(__name__)

# Load configuration from YAML file
with open( sys.argv[1], "r") as f:
    config = yaml.safe_load(f)

# Configure basic authentication
app.config['BASIC_AUTH_USERNAME'] = config['username']
app.config['BASIC_AUTH_PASSWORD'] = config['password']
basic_auth = BasicAuth(app)

@app.route('/meeting/csv')
@basic_auth.required
def get_csv():
    # Open the CSV file
    with open(config['csv_path'], 'r') as file:
        reader = csv.reader(file)
        data = list(reader)

    # Create a string buffer to write the CSV data to
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)

    # Write the data to the CSV buffer
    for row in data:
        writer.writerow(row)

    # Set the content type to CSV and return the CSV data as a response
    response = Response(csv_buffer.getvalue(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="data.csv")
    return response

@app.route('/meeting/next')
@basic_auth.required
def get_next_meeting():
    
    response_data = {
        'description': next_meeting['description'],
        'start': next_meeting['start']
    }
    return jsonify(response_data)

def get_file_mtime(file_path):
    mtime = os.path.getmtime(file_path)
    timestamp = datetime.datetime.fromtimestamp(mtime)
    timestamp = timestamp.replace(microsecond=0)
    return timestamp

def parse_version(version_string):
    parts = version_string.split('-')
    if len(parts) != 3:
        raise ValueError('Invalid version string')
    filename, date_str, time_str = parts
    date_time_str = f"{date_str.strip()} {time_str.strip()}"
    try:
        timestamp = datetime.datetime.strptime(date_time_str, '%b %d %Y %H:%M:%S')
        timestamp = timestamp.replace(microsecond=0)
    except ValueError:
        raise ValueError('Invalid version string')
    return filename, timestamp

@app.route(config['route_firmware'], methods=['GET'])
def get_firmware():
    firmware_version = request.headers.get('x-ESP8266-version')
    if not firmware_version:
        return 'Firmware version not specified', 400
    try:
        filename, firmware_version_mtime = parse_version(firmware_version)
    except ValueError:
        return 'Invalid firmware version', 400
    filepath = os.path.join(config['route_firmware_dir'], filename + '.bin')
    if not os.path.isfile(filepath):
        return 'Firmware not found', 404
    firmware_file_mtime = get_file_mtime(filepath)
    if firmware_file_mtime > firmware_version_mtime:
        return send_file(filepath, as_attachment=True, mimetype='application/octet-stream')
    else:
        return '', 304  # Not Modified
    
if __name__ == '__main__':
    app.run(debug=True,port=config['port'])


