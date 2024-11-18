#!/bin/bash
# executed with root
echo -e "Starting Samba..."
setfacl -R -m "g:samba:rwx" ${HOME}/recordings
/usr/sbin/smbd -D  
/usr/sbin/nmbd -D 

# change bind mount ownership to zoomrec
chown -R zoomrec:zoomrec ${HOME}/recordings
chown -R zoomrec:zoomrec ${HOME}/audioexit

# start application witwith non-root
echo -e "Starting Zoomrec..."
exec su zoomrec -p -c "${START_DIR}/starting.sh"