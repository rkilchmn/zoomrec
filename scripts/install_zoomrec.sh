#!/bin/bash

read -p "Do you want to continue with zoomrec setup? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborting zoomrec setup."
  exit 1
fi

# Show usage help
show_help() {
  echo "Usage: $0 <ZOOMREC_HOME> <TYPE> [ACCELERATION]"
  echo ""
  echo "Parameters:"
  echo "  ZOOMREC_HOME   Path to install/setup zoomrec (e.g., /opt/zoomrec)"
  echo "  TYPE           CLIENT | SERVER | BOTH"
  echo "  ACCELERATION   VAAPI | NVIDIA | (blank for none)"
  echo ""
  echo "Example:"
  echo "  $0 /opt/zoomrec BOTH VAAPI"
  exit 1
}

# Check for required parameters
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Error: Missing required parameters."
  show_help
fi

ZOOMREC_HOME=$1
TYPE=$2
ACCELERATION=$3

# Validate TYPE
if [[ "$TYPE" != "CLIENT" && "$TYPE" != "SERVER" && "$TYPE" != "BOTH" ]]; then
  echo "Error: TYPE must be CLIENT, SERVER, or BOTH."
  show_help
fi

# Validate ACCELERATION
if [[ -n "$ACCELERATION" && "$ACCELERATION" != "VAAPI" && "$ACCELERATION" != "NVIDIA" ]]; then
  echo "Error: ACCELERATION must be VAAPI, NVIDIA, or blank."
  show_help
fi

echo "[INFO] Setting up zoomrec environment at $ZOOMREC_HOME"
mkdir -p "$ZOOMREC_HOME"

# Create zoomrec user if not exists
if id "zoomrec" &>/dev/null; then
  echo "[INFO] User 'zoomrec' already exists."
else
  echo "[INFO] Creating user 'zoomrec'"
  useradd -s /bin/bash -d "$ZOOMREC_HOME" -m -u 1999 zoomrec
  passwd zoomrec
fi

# Add user to docker group
usermod -aG docker zoomrec

# VAAPI setup
if [ "$ACCELERATION" == "VAAPI" ]; then
  usermod -aG video zoomrec
  usermod -aG render zoomrec
fi

mkdir -p "$ZOOMREC_HOME/logs"

if [ "$TYPE" == "CLIENT" ] || [ "$TYPE" == "BOTH" ]; then
  echo "[INFO] Setting up CLIENT components"
  mkdir -p "$ZOOMREC_HOME/recordings"
  mkdir -p "$ZOOMREC_HOME/audio"
  mkdir -p "$ZOOMREC_HOME/logs/screenshots"

  cp -r example/audio "$ZOOMREC_HOME"
  cp -r res/img "$ZOOMREC_HOME"
  cp example/config_client_example.txt "$ZOOMREC_HOME/config_client.txt"
fi

if [ "$TYPE" == "SERVER" ] || [ "$TYPE" == "BOTH" ]; then
  echo "[INFO] Setting up SERVER components"
  mkdir -p "$ZOOMREC_HOME/firmware"

  mkdir -p /root/sftp-data
  chown root:root /root/sftp-data
  chmod 755 /root/sftp-data

  cp example/config_server_example.txt "$ZOOMREC_HOME/config_server.txt"
  cp example/email_types_example.yaml "$ZOOMREC_HOME/email_types.yaml"

  if [ ! -f "$ZOOMREC_HOME/zoomrec_server_db" ]; then
    touch "$ZOOMREC_HOME/zoomrec_server_db"
  fi
fi

chown -R zoomrec:zoomrec "$ZOOMREC_HOME"
chmod -R 755 "$ZOOMREC_HOME"

echo "[INFO] Setup complete."
