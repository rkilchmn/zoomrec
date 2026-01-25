#!/usr/bin/env python3
import os
import sys
import pwd
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv
from shared.constants import (
    CONFIG_DIR, SFTP_CONFIG_DIR, AUTOMATION_DIR, IMG_DIR, AUDIO_DIR,
    RECORDINGS_DIR, LOG_DIR, SCREENSHOT_DIR, SFTP_KNOWN_HOSTS_FILE,
    SFTP_HOST_KEY_FILE, SFTP_ADMIN_USER_IDENTITY_FILE, ARDUINO_FIRMWARE_DIR,
    ARDUINO_CONFIG_DIR, SFTP_DATA_PATH, SFTP_ADMIN_USERNAME, EMAIL_CONFIG_FILE,
    ZOOMREC_USER, DEFAULT_ZOOMREC_USER_GID
)

def copy_if_not_exists(src, dst):
    """Copy file from src to dst only if dst doesn't exist."""
    dst_path = Path(dst)
    if not dst_path.exists():
        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logging.info(f"Copied {src} to {dst}")
    else:
        logging.info(f"Skipping {dst} - already exists")

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def show_help():
    """Show usage help and exit."""
    print(f"Usage: {sys.argv[0]} <ZOOMREC_HOME> <TYPE> [ACCELERATION]")
    print("")
    print("Parameters:")
    print(f"  ZOOMREC_HOME   Path to install/setup {ZOOMREC_USER} (e.g., /home/{ZOOMREC_USER})")
    print("  COMPONENT      CLIENT | SERVER | BOTH")
    print("  ACCELERATION   VAAPI | NVIDIA | (blank for none)")
    print("")
    print("Example:")
    print(f"  {sys.argv[0]} /home/{ZOOMREC_USER} BOTH VAAPI")
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
        logging.error("Error: COMPONENT must be CLIENT, SERVER, or BOTH.")
        show_help()

    if acceleration and acceleration not in ["VAAPI"]:
        logging.error("Error: ACCELERATION must be VAAPI or blank.")
        show_help()

    return zoomrec_home, install_type, acceleration

def setup_user(zoomrec_home):
    """Create zoomrec user if not exists and set up groups."""
    try:
        pwd.getpwnam(ZOOMREC_USER)
        logging.info(f"User '{ZOOMREC_USER}' exists.")
        return True
    except KeyError:
        ZOOMREC_USER_GID = os.getenv('ZOOMREC_USER_GID',DEFAULT_ZOOMREC_USER_GID)
        logging.info(f"User '{ZOOMREC_USER}' does not exist. It needs to be created manually:")
        logging.info("=== User Setup (requires sudo) ===")
        logging.info(f"# Create {ZOOMREC_USER} user and set password:")
        logging.info(f"sudo useradd -s /bin/bash -m -u {ZOOMREC_USER_GID} -U {ZOOMREC_USER}")
        logging.info(f"sudo passwd {ZOOMREC_USER}")
        logging.info("# Add user to docker group")
        logging.info(f"sudo usermod -aG docker {ZOOMREC_USER}")
        logging.info("=================================")
        logging.info(f"After user '{ZOOMREC_USER}' is created, switch to user '{ZOOMREC_USER}', clone the repo and rerun the install script.")
        return False

def setup_client(zoomrec_home, acceleration):
    """Set up client components."""
    logging.info("")
    logging.info("Setting up CLIENT components")
    
    # Create mandatory config subdirectories 
    os.makedirs(os.path.join(zoomrec_home, CONFIG_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, SFTP_CONFIG_DIR), exist_ok=True)

    # Create optional paths for automation
    os.makedirs(os.path.join(zoomrec_home, CONFIG_DIR, AUTOMATION_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, AUDIO_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, CONFIG_DIR, AUTOMATION_DIR, 'zoom'), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, CONFIG_DIR, AUTOMATION_DIR, 'zoom', IMG_DIR), exist_ok=True)
    
    # Create required data subdirectories
    os.makedirs(os.path.join(zoomrec_home, RECORDINGS_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, LOG_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, SCREENSHOT_DIR), exist_ok=True)

    # Set up SFTP known hosts with server's public key
    known_hosts_path = os.path.join(zoomrec_home, SFTP_KNOWN_HOSTS_FILE)
    sftp_key_path = os.path.join(zoomrec_home, SFTP_HOST_KEY_FILE)
    
    if not os.path.exists(known_hosts_path):
        # Add server's public key to known_hosts
        if os.path.exists(f"{sftp_key_path}.pub"):
            with open(f"{sftp_key_path}.pub", 'r') as key_file, open(known_hosts_path, 'w') as f:
                key_data = key_file.read().strip().split()
                if len(key_data) >= 2:
                    hostname = "zoomrec_server"
                    key_type = key_data[0]
                public_key = key_data[1]
                f.write(f"{hostname} {key_type} {public_key}\n")
            os.chmod(known_hosts_path, 0o600)
            logging.info(f"Added SFTP server public key to {known_hosts_path}")
        else:
            logging.info(f"SFTP server public key not found. Copy it from the server to {sftp_key_path}.pub and rerun the install script.")
        
    # check admin private key
    admin_key_path = os.path.join(zoomrec_home, SFTP_ADMIN_USER_IDENTITY_FILE)
    if not os.path.exists(admin_key_path):
        logging.info(f"SFTP admin private key not found. Copy it from the server to {admin_key_path} and rerun the install script to verify this error is resolved.")

    # Copy example files
    copy_if_not_exists('example/.env', os.path.join(zoomrec_home, '.env'))
    copy_if_not_exists('example/.client.env', os.path.join(zoomrec_home, '.client.env'))
    copy_if_not_exists('example/.server.env', os.path.join(zoomrec_home, '.server.env')) # required for composer stop command

    if acceleration == "VAAPI":
        logging.info("=== VAAPI Acceleration Setup (requires root) ===")
        logging.info(f"# Add '{ZOOMREC_USER}' user to video and render groups for VAAPI acceleration:")
        logging.info(f"sudo usermod -aG video {ZOOMREC_USER}")
        logging.info(f"sudo usermod -aG render {ZOOMREC_USER}")
        logging.info("==========================================")

def setup_server(zoomrec_home):
    """Set up server components."""
    logging.info("")
    logging.info("Setting up SERVER components")
    
    # Create config directories
    os.makedirs(os.path.join(zoomrec_home, ARDUINO_FIRMWARE_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, ARDUINO_CONFIG_DIR), exist_ok=True)
    os.makedirs(os.path.join(zoomrec_home, SFTP_CONFIG_DIR), exist_ok=True)

    # Generate SFTP host key if it doesn't exist
    sftp_key_path = os.path.join(zoomrec_home, SFTP_HOST_KEY_FILE)
    if not os.path.exists(sftp_key_path):
        os.makedirs(os.path.dirname(sftp_key_path), exist_ok=True)
        os.system(f'ssh-keygen -t ed25519 -f {sftp_key_path} -N ""')
        logging.info("Generated SFTP host key")

    # Set proper permissions on the SFTP key directory 
    sftp_config_dir = os.path.join(zoomrec_home, SFTP_CONFIG_DIR)
    os.chmod(sftp_config_dir, 0o700)
    if os.path.exists(sftp_key_path):
        os.chmod(sftp_key_path, 0o600)
    if os.path.exists(f"{sftp_key_path}.pub"):
        os.chmod(f"{sftp_key_path}.pub", 0o644)    

    # Create required data subdirectories
    os.makedirs(os.path.join(zoomrec_home, LOG_DIR), exist_ok=True)

    # Copy example files if they don't exist
    copy_if_not_exists('example/.env', os.path.join(zoomrec_home, '.env'))
    copy_if_not_exists('example/.server.env', os.path.join(zoomrec_home, '.server.env'))
    copy_if_not_exists('example/.client.env', os.path.join(zoomrec_home, '.client.env'))  # required for composer stop command
    copy_if_not_exists('example/email_types.yaml', os.path.join(zoomrec_home, EMAIL_CONFIG_FILE))
   
    # These commands require root privileges - please run them manually:
    logging.info("")
    logging.info("=== [OPTIONAL] SFTP Server Setup (requires sudo) ===")
    logging.info(f"# Create and set up SFTP data directory:")
    logging.info(f"sudo mkdir -p {SFTP_DATA_PATH}")
    logging.info(f"sudo chown root:root {SFTP_DATA_PATH}")
    logging.info(f"sudo chmod 755 {SFTP_DATA_PATH}")
    
    # Load environment variables (required by sftp_user_create_command)
    load_dotenv(os.path.join(zoomrec_home, '.env')) 
    from shared.sftp_user import sftp_user_create_command
    # Get the SFTP user creation command and log it
    cmd = sftp_user_create_command(SFTP_ADMIN_USERNAME)
    logging.info("# Create SFTP admin user:")
    logging.info(" ".join(cmd))
    
    # Command to copy the admin's private key
    admin_key_path = os.path.join(zoomrec_home, SFTP_ADMIN_USER_IDENTITY_FILE)
    logging.info("# Copy 'zoomrec' admin's private key (run as root):")
    logging.info(f"sudo cp {SFTP_DATA_PATH}/{SFTP_ADMIN_USERNAME}/.ssh/id_rsa {admin_key_path}")
    logging.info(f"sudo chown {ZOOMREC_USER}:{ZOOMREC_USER} {admin_key_path}")
    logging.info(f"chmod 600 {admin_key_path}")
    logging.info("===========================================")

def main():
    # Get and validate command line arguments
    zoomrec_home, component, acceleration = validate_args()
    logging.info("")

    # Set up user and groups
    if setup_user(zoomrec_home):
        logging.info(f"Setting up zoomrec environment at {zoomrec_home}")

        # Create base directory
        os.makedirs(zoomrec_home, exist_ok=True)
        
        if component in ["SERVER", "BOTH"]:
            setup_server(zoomrec_home)

        if component in ["CLIENT", "BOTH"]:
            setup_client(zoomrec_home, acceleration)

        # # Set final permissions
        # os.system(f'chown -R {ZOOMREC_USER}:{ZOOMREC_USER} {zoomrec_home}')
        # os.system(f'chmod -R 755 {zoomrec_home}')

        logging.info("Setup complete.")
        logging.info("IMPORTANT: Re-login to apply group changes.")
    
if __name__ == "__main__":
    main()
