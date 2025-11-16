# Base Image
FROM ubuntu:24.04

ARG ZOOMREC_USER_ID=""
ARG ZOOMREC_USER_GID=""

ENV PYTHON_VENV_PATH="/python/venv"

ENV DEBIAN_FRONTEND=noninteractive

ENV HOME=/home/zoomrec \
    ZOOMREC_HOME=/home/zoomrec \
    TZ=Etc/UTC

# Install Python, SSH, sudo, and required packages
RUN apt update && apt install -y \
    python3-full \
    python3-venv \
    openssh-server \
    libpam-python \
    inetutils-syslogd \
    curl \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment
RUN mkdir -p ${PYTHON_VENV_PATH} && \
    python3 -m venv ${PYTHON_VENV_PATH}

ENV PATH=${PYTHON_VENV_PATH}/bin:$PATH

# Create zoomrec user and add to sudoers
RUN groupadd -g ${ZOOMREC_USER_GID} zoomrec
RUN useradd -ms /bin/bash -u ${ZOOMREC_USER_ID} -g zoomrec -d ${HOME} zoomrec
RUN echo "zoomrec ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/zoomrec
RUN chmod 0440 /etc/sudoers.d/zoomrec

# Set the working directory
WORKDIR ${HOME}

# Copy and install Python dependencies for server
COPY server/requirements.txt ${HOME}/server/requirements.txt
RUN pip install --no-cache-dir -r ${HOME}/server/requirements.txt

# Create server directory python and app scripts
RUN mkdir -p ${HOME}/server
COPY server/* ${HOME}/server/
RUN chmod +x ${HOME}/server/*.sh
# copy templates
COPY server/res/*.html ${HOME}/server/res/
COPY server/res/*.txt ${HOME}/server/res/


# Copy and install Python dependencies for shared
COPY shared/requirements.txt ${HOME}/shared/requirements.txt
RUN pip install --no-cache-dir -r ${HOME}/shared/requirements.txt

# Create shared directory python and app scripts
RUN mkdir -p ${HOME}/shared
COPY shared/* ${HOME}/shared/
RUN chmod +x ${HOME}/shared/*.sh

# install as package for correct imports
COPY setup.py ${HOME}/
RUN pip install -e ${HOME}

# copy server entrypoint
COPY server/res/entrypoint.sh ${HOME}/
RUN chmod +x ${HOME}/entrypoint.sh

# Create necessary directories for SSH and logs
RUN mkdir -p /var/run/sshd /usr/local/bin

# set up the SFTP authentication script
RUN chmod +x ${HOME}/server/pam_sftp.py

# Set ownership of the home directory
RUN chown -R zoomrec:zoomrec ${HOME}

# Configure PAM to use the custom authentication script
RUN echo "auth sufficient  pam_python.so ${HOME}/server/pam_sftp.py" > /etc/pam.d/sshd && \
    echo "account optional pam_python.so ${HOME}/server/pam_sftp.py" >> /etc/pam.d/sshd && \
    echo "session optional pam_python.so ${HOME}/server/pam_sftp.py" >> /etc/pam.d/sshd

# Configure SSH for SFTP-only access and PAM authentication
RUN sed -i "s/#UsePAM no/UsePAM yes/" /etc/ssh/sshd_config && \
    sed -i "s/PasswordAuthentication no/PasswordAuthentication yes/" /etc/ssh/sshd_config && \
    sed -i "s/#ChallengeResponseAuthentication yes/ChallengeResponseAuthentication yes/" /etc/ssh/sshd_config && \
    sed -i "s/^#SyslogFacility.*$/SyslogFacility AUTH/" /etc/ssh/sshd_config && \
    sed -i "s/^#LogLevel.*$/LogLevel DEBUG/" /etc/ssh/sshd_config && \
    echo "HostKey ${HOME}/config/sftp/sftp_host_key" >> /etc/ssh/sshd_config && \
    echo "Subsystem sftp internal-sftp -l DEBUG" >> /etc/ssh/sshd_config && \
    echo "Match User *,!zoomrec_admin" >> /etc/ssh/sshd_config && \
    echo "    ChrootDirectory /root/sftp-data/%u" >> /etc/ssh/sshd_config && \
    echo "    ForceCommand internal-sftp" >> /etc/ssh/sshd_config && \
    echo "    AllowTcpForwarding no" >> /etc/ssh/sshd_config && \
    echo "    X11Forwarding no" >> /etc/ssh/sshd_config && \
    echo "Match User zoomrec_admin" >> /etc/ssh/sshd_config && \
    echo "    ChrootDirectory /root/sftp-data" >> /etc/ssh/sshd_config && \
    echo "    ForceCommand internal-sftp" >> /etc/ssh/sshd_config && \
    echo "    AllowTcpForwarding no" >> /etc/ssh/sshd_config && \
    echo "    X11Forwarding no" >> /etc/ssh/sshd_config

# Expose SFTP and API ports
EXPOSE $SERVER_PORT
EXPOSE $SSH_PORT

# Set the entrypoint to run the startup script
CMD ["/bin/sh", "-c", "${HOME}/entrypoint.sh"]