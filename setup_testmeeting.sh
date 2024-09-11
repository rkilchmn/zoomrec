#!/bin/bash

# Get Zoom API credentials from environment variables
ZOOM_CLIENT_ID="${ZOOM_CLIENT_ID}"
ZOOM_CLIENT_SECRET="${ZOOM_CLIENT_SECRET}"
REDIRECT_URI="http://localhost:8080/oauth/callback"  # Your redirect URI

# Calculate start time (current time + 15 minutes)
START_TIME=$(date -u -d "+15 minutes" +"%Y-%m-%dT%H:%M:%SZ")

cess token using authorization_code grant type
ZOO"$ZOOM_CLIENT_ID:$ZOOM_CLIENT_SECRET" | base64)" \
     -d "grant_type=authorization_code&code=$AUTHORIZATION_CODE&redirect_uri=$REDIRECT_URI" \
     | jq -r '.access_token')

# Debug: Print the token response
echo "Zoom Token Response: $ZOOM_TOKEN"

# Create Zoom meeting with additional parameters using the received access token
ZOOM_RESPONSE=$(curl -s -X POST "https://api.zoom.us/v2/users/me/meetings" \
     -H "Authorization: Bearer $ZOOM_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
        "topic": "Test Meeting",
        "type": 2,
        "start_time": "'"$START_TIME"'",
        "duration": 30,
        "timezone": "America/New_York",
        "password": "123456",
        "agenda": "Discuss the project progress.",
        "settings": {
          "host_video": true,
          "participant_video": true,
          "join_before_host": false,
          "mute_upon_entry": true,
          "waiting_room": true
        }
     }')

# Debug: Print the raw response from Zoom API
echo "Zoom API Response: $ZOOM_RESPONSE"

# Extract meeting details
MEETING_ID=$(echo $ZOOM_RESPONSE | jq -r '.id')
JOIN_URL=$(echo $ZOOM_RESPONSE | jq -r '.join_url')

# Check if Meeting ID and Join URL are null
if [ "$MEETING_ID" == "null" ] || [ "$JOIN_URL" == "null" ]; then
    echo "Error: Failed to create Zoom meeting. Please check the API response."
    echo "Response Details: $ZOOM_RESPONSE"
    exit 1
fi

# Format date and time for Flask app
MEETING_DATE=$(date -u -d "$START_TIME" +"%d/%m/%Y")
MEETING_TIME=$(date -u -d "$START_TIME" +"%H:%M")

# Call Flask app to create event
FLASK_RESPONSE=$(curl -s -u "$FLASK_USER:$FLASK_PASSWORD" -X POST \
     -H "Content-Type: application/json" \
     -d '{
        "description": "Test Meeting",
        "weekday": "'"$MEETING_DATE"'",
        "time": "'"$MEETING_TIME"'",
        "timezone": "America/New_York",
        "duration": "30",
        "record": "true",
        "id": "'"$JOIN_URL"'"
     }' \
     "$FLASK_URL")

echo "Zoom Meeting Created:"
echo "Meeting ID: $MEETING_ID"
echo "Join URL: $JOIN_URL"
echo
echo "Flask App Response:"
echo $FLASK_RESPONSE
