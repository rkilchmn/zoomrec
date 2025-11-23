#!/bin/bash

# Step to event ID mapping
declare -A STEP_TO_EVENT_ID=(
    ["transcribe"]=21
    ["custom"]=27
    ["upload"]=39
)

usage() {
    echo "Usage: $0 <workflow-id> <step-to-skip>"
    echo "Available steps: ${!STEP_TO_EVENT_ID[*]}"
    echo "Example:"
    echo "  $0 workflow-id transcribe"
    echo "  $0 workflow-id custom"
    echo "  $0 workflow-id upload"
}

# Validate input
if [ "$#" -ne 2 ]; then
    usage
    exit 1
fi

WORKFLOW_ID=$1
STEP=$2

# Validate the step
if [[ -z "${STEP_TO_EVENT_ID[$STEP]}" ]]; then
    echo "Error: Invalid step '$STEP'"
    echo "Available steps: ${!STEP_TO_EVENT_ID[*]}"
    exit 1
fi

# Get the event ID for the step
EVENT_ID=${STEP_TO_EVENT_ID[$STEP]}

# Create JSON array with the step to skip
JSON_INPUT="[\"$STEP\"]"

echo "Sending skip signal for step: $STEP (event ID: $EVENT_ID)"

docker exec -u zoomrec zoomrec_client /home/zoomrec/.temporalio/bin/temporal \
    workflow signal \
    --workflow-id "$WORKFLOW_ID" \
    --name skipSteps \
    --input "$JSON_INPUT"

echo "Resetting workflow to before step: $STEP"
docker exec -u zoomrec zoomrec_client /home/zoomrec/.temporalio/bin/temporal \
    workflow reset \
    --namespace default \
    --workflow-id "$WORKFLOW_ID" \
    --event-id "$((EVENT_ID - 1))" \
    --reason "Reset to before $STEP step"