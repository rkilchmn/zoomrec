#!/usr/bin/env python3
import os
import sys
import pwd
import shutil
import logging
from pathlib import Path
from shared.constants import (
    SFTP_DATA_PATH,
    RECORDINGS_DIR,
    AUDIO_DIR,
    IMG_DIR,
    LOG_DIR,
    DEBUG_DIR,
    FIRMWARE_DIR,
    ZOOMREC_DB_FILENAME,
)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def show_help():
    """Show usage help and exit."""
    print(f"Usage: {sys.argv[0]} <ZOOMREC_HOME> <TYPE> [ACCELERATION]")
    print("")
    print("Parameters:")
    print("  ZOOMREC_HOME   Path to install/setup zoomrec (e.g., /home/zoomrec)")
    print("  TYPE           CLIENT | SERVER | BOTH")
    print("  ACCELERATION   VAAPI | NVIDIA | (blank for none)")
    print("")
    print("Example:")
    print(f"  {sys.argv[0]} /home/zoomrec BOTH VAAPI")
    sys.exit(1)

def validate_args():
    """Validate command line arguments."""
    if len(sys.argv) < 3:
        logging.error("Error: Missing required parameters.")
        show_help()

    zoomrec_home = sys.argv[1]
    install_type = sys.argv[2].upper()
    acceleration = sys.argv[3].upper() if len(sys.argv) > 3 else None

    if install_type not in ["CLIENT", "SERVER", "BOTH"]:
        logging.error("Error: TYPE must be CLIENT, SERVER, or BOTH.")
        show_help()

    if acceleration and acceleration not in ["VAAPI", "NVIDIA"]:
        logging.error("Error: ACCELERATION must be VAAPI, NVIDIA, or blank.")
        show_help()

    return zoomrec_home, install_type, acceleration

def setup_user(zoomrec_home):
    """Create zoomrec user if not exists and set up groups."""
    try:
        pwd.getpwnam('zoomrec')
        logging.info("User 'zoomrec' already exists.")
    except KeyError:
        logging.info("Creating user 'zoomrec'")
        os.system(f'useradd -s /bin/bash -d "{zoomrec_home}" -m -u 1999 zoomrec')
        os.system('passwd zoomrec')

    # Add user to docker group
    os.system('usermod -aG docker zoomrec')

def setup_client(zoomrec_home):
    """Set up client components."""
    logging.info("Setting up CLIENT components")
    
    # Create required directories
    os.makedirs(os.path.join(zoomrec_home, RECORDINGS_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, AUDIO_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, LOG_DIR, DEBUG_DIR), exist_ok=True)

    # Copy example files
    shutil.copytree('example/audio', os.path.join(zoomrec_home, AUDIO_DIR), dirs_exist_ok=True)
    shutil.copytree('res/img', os.path.join(zoomrec_home, IMG_DIR), dirs_exist_ok=True)
    shutil.copy('example/email_types.yaml', os.path.join(zoomrec_home, 'email_types.yaml'))
    shutil.copy('example/.client.env', os.path.join(zoomrec_home, '.client.env'))
    shutil.copy('example/.env', os.path.join(zoomrec_home, '.env'))

def setup_server(zoomrec_home):
    """Set up server components."""
    logging.info("Setting up SERVER components")
    
    # Create required directories
    os.makedirs(os.path.join(zoomrec_home, FIRMWARE_DIR), exist_ok=True)
    os.makedirs(SFTP_DATA_PATH, exist_ok=True)

    # Set SFTP directory permissions
    os.chown(SFTP_DATA_PATH, 0, 0)  # root:root
    os.chmod(SFTP_DATA_PATH, 0o755)

    # Copy example files
    shutil.copy('example/.server.env', os.path.join(zoomrec_home, '.server.env'))
    shutil.copy('example/.env', os.path.join(zoomrec_home, '.env'))

    # Create empty database file if it doesn't exist
    db_path = os.path.join(zoomrec_home, ZOOMREC_DB_FILENAME)
    if not os.path.exists(db_path):
        Path(db_path).touch()

def main():
    zoomrec_home, *_ = validate_args()  # Only use ZOOMREC_HOME from CLI, use interactive for rest
    component, acceleration = get_user_setup_options()
    logging.info(f"Setting up zoomrec environment at {zoomrec_home}")

    # Create base directory
    os.makedirs(zoomrec_home, exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, LOG_DIR), exist_ok=True)

    # Set up user and groups
    setup_user(zoomrec_home)

    # Set up VAAPI acceleration if requested
    if acceleration == "VAAPI":
        os.system('usermod -aG video zoomrec')
        os.system('usermod -aG render zoomrec')

    # Set up components based on selected component type
    if component in ["CLIENT", "BOTH"]:
        setup_client(zoomrec_home)

    if component in ["SERVER", "BOTH"]:
        setup_server(zoomrec_home)

    # Set final permissions
    os.system(f'chown -R zoomrec:zoomrec {zoomrec_home}')
    os.system(f'chmod -R 755 {zoomrec_home}')

    logging.info("Setup complete.")
    logging.info("IMPORTANT: Re-login to apply group changes.")
    
if __name__ == "__main__":
    main()
