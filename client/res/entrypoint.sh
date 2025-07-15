#!/bin/bash
# executed with root
echo -e "Starting Samba..."
setfacl -R -m "g:samba:rwx" ${HOME}/data/recordings
/usr/sbin/smbd -D  
/usr/sbin/nmbd -D 

# change bind mount ownership to zoomrec
# chown -R zoomrec:zoomrec ${HOME}/data
# chown -R zoomrec:zoomrec ${HOME}/config

# start application witwith non-root
echo -e "Starting Zoomrec..."
exec su zoomrec -p -c "${START_DIR}/starting.sh"