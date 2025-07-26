#!/bin/bash
# executed with root
echo -e "Starting Samba..."

# Create Samba user and group
if [ -n "$SAMBA_USERNAME" ]; then
    echo "Creating Samba user $SAMBA_USERNAME and group samba..."
    groupadd samba 2>/dev/null || true
    id -u $SAMBA_USERNAME &>/dev/null || useradd $SAMBA_USERNAME
    usermod -aG samba $SAMBA_USERNAME
fi

# Create Samba user and set password
if [ -n "$SAMBA_PASSWORD" ]; then
    echo -e "Creating Samba user $SAMBA_USERNAME..."
    (echo "$SAMBA_PASSWORD"; echo "$SAMBA_PASSWORD") | smbpasswd -a -s $SAMBA_USERNAME
fi

# Set permissions for recordings directory
setfacl -R -m "g:samba:rwx" ${HOME}/data/recordings

# Start Samba services
/usr/sbin/smbd -D  
/usr/sbin/nmbd -D 

# change bind mount ownership to zoomrec
# chown -R zoomrec:zoomrec ${HOME}/data
# chown -R zoomrec:zoomrec ${HOME}/config

# start application with non-root
echo -e "Starting Zoomrec..."
exec su zoomrec -p -c "${START_DIR}/starting.sh"