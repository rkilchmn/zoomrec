# Base Image
FROM ubuntu:24.04

ENV PYTHON_VENV_PATH="/python/venv"

ENV DEBIAN_FRONTEND=noninteractive

ENV HOME=/home/zoomrec \
    ZOOMREC_HOME=/home/zoomrec \
    TZ=Etc/UTC \
    SERVER_USERNAME="myuser" \
    SERVER_PASSWORD="mypassword"

# Install Python, SSH, sudo, and required packages
RUN apt update && apt install -y \
    python3-full \
    python3-venv \
    openssh-server \
    libpam-python \
    inetutils-syslogd \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment
RUN mkdir -p ${PYTHON_VENV_PATH} && \
    python3 -m venv ${PYTHON_VENV_PATH}

ENV PATH=${PYTHON_VENV_PATH}/bin:$PATH

# Create zoomrec user and add to sudoers
RUN useradd -ms /bin/bash -u 1999 zoomrec -d ${HOME} && \
    echo "zoomrec ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/zoomrec && \
    chmod 0440 /etc/sudoers.d/zoomrec

# Set the working directory
WORKDIR ${HOME}

# Copy and install Python dependencies
COPY server/requirements.txt ${HOME}/
RUN pip install --no-cache-dir -r ${HOME}/requirements.txt

# Copy application files
COPY zoomrec_server.py zoomrec_server_app.py gunicorn_conf.py telegram_bot.py imap_bot.py \
     events.py events_api.py users.py users_api.py msg_telegram.py constants.py password.py utilities.py \
     zoomrec_server_app.yaml ${HOME}/

# Copy and set up the startup script
COPY server/entrypoint.sh ${HOME}/
RUN chmod +x ${HOME}/entrypoint.sh

# Copy and set up the startup script
COPY server/create-sftp-user.sh ${HOME}/
RUN chmod +x ${HOME}/create-sftp-user.sh

# Create necessary directories for SSH and logs
RUN mkdir -p /var/run/sshd /usr/local/bin ${HOME}/sftp-data/sftpuser1/recordings

# Copy and set up the SFTP authentication script
COPY server/pam_sftp.py ${HOME}/
RUN chmod +x ${HOME}/pam_sftp.py

# Set ownership of the home directory
RUN chown -R zoomrec:zoomrec ${HOME}

# Configure PAM to use the custom authentication script
RUN echo "auth sufficient  pam_python.so ${HOME}/pam_sftp.py" > /etc/pam.d/sshd && \
    echo "account optional pam_python.so ${HOME}/pam_sftp.py" >> /etc/pam.d/sshd && \
    echo "session optional pam_python.so ${HOME}/pam_sftp.py" >> /etc/pam.d/sshd

# Configure SSH for SFTP-only access and PAM authentication
RUN sed -i 's/#UsePAM no/UsePAM yes/' /etc/ssh/sshd_config && \
    sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#ChallengeResponseAuthentication yes/ChallengeResponseAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/^#SyslogFacility.*$/SyslogFacility AUTH/' /etc/ssh/sshd_config && \
    sed -i 's/^#LogLevel.*$/LogLevel DEBUG/' /etc/ssh/sshd_config && \
    echo 'Subsystem sftp internal-sftp -l DEBUG' >> /etc/ssh/sshd_config && \
    echo 'Match User *,!zoomrec_admin' >> /etc/ssh/sshd_config && \
    echo "    ChrootDirectory /root/sftp-data/%u" >> /etc/ssh/sshd_config && \
    echo '    ForceCommand internal-sftp' >> /etc/ssh/sshd_config && \
    echo '    AllowTcpForwarding no' >> /etc/ssh/sshd_config && \
    echo '    X11Forwarding no' >> /etc/ssh/sshd_config && \
    echo 'Match User zoomrec_admin' >> /etc/ssh/sshd_config && \
    echo "    ChrootDirectory /root/sftp-data" >> /etc/ssh/sshd_config && \
    echo '    ForceCommand internal-sftp' >> /etc/ssh/sshd_config && \
    echo '    AllowTcpForwarding no' >> /etc/ssh/sshd_config && \
    echo '    X11Forwarding no' >> /etc/ssh/sshd_config

# Expose SFTP and API ports
EXPOSE 22
EXPOSE $DOCKER_API_PORT

# Set the entrypoint to run the startup script
CMD ["/bin/sh", "-c", "${HOME}/entrypoint.sh"]