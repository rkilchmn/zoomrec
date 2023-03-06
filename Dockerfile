FROM ubuntu:20.04

ENV HOME=/home/zoomrec \
    TZ=Europe/Berlin \
    TERM=xfce4-terminal \
    START_DIR=/start \
    DEBIAN_FRONTEND=noninteractive \
    VNC_RESOLUTION=1024x576 \
    VNC_COL_DEPTH=24 \
    VNC_PW=zoomrec \
    VNC_PORT=5901 \
    DISPLAY=:1 \
    FFMPEG_INPUT_PARAMS="" \
    FFMPEG_OUTPUT_PARAMS="-acodec pcm_s16le -vcodec libx264rgb -preset ultrafast -crf 0" \
    LIBVA_DRIVER_NAME=iHD \
    SAMBA_USER=testuser \
    SAMBA_PASS=test123 \
    IMAP_SERVER="" \
    IMAP_PORT="" \
    EMAIL_ADDRESS="" \
    EMAIL_PASSWORD="" 

# Add user
RUN useradd -ms /bin/bash zoomrec -d ${HOME}
WORKDIR ${HOME}

ADD res/requirements.txt ${HOME}/res/requirements.txt

# Install some tools
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        apt \
        apt-utils \
        ca-certificates \
        publicsuffix \
        libapt-pkg6.0 \
        libpsl5 \
        libssl1.1 \
        libnss3 \
        openssl \
        wget \
        locales \
        bzip2 \
        tzdata && \
# Generate locales for en_US.UTF-8
    locale-gen en_US.UTF-8 && \
# Install tigervnc
    wget -q -O tigervnc-1.10.0.x86_64.tar.gz https://sourceforge.net/projects/tigervnc/files/stable/1.10.0/tigervnc-1.10.0.x86_64.tar.gz && \
    tar xz -f tigervnc-1.10.0.x86_64.tar.gz --strip 1 -C / && \
    rm -rf tigervnc-1.10.0.x86_64.tar.gz && \
# Install xfce ui
    apt-get install --no-install-recommends -y \
        supervisor \
        xfce4 \
        xfce4-goodies \
        xfce4-pulseaudio-plugin \
        xfce4-terminal \
        xubuntu-icon-theme && \
# Install pulseaudio
    apt-get install --no-install-recommends -y \
        pulseaudio \
        pavucontrol && \
# Install necessary packages
    apt-get install --no-install-recommends -y \
        ibus \
        dbus-user-session \
        dbus-x11 \
        dbus \
        at-spi2-core \
        xauth \
        x11-xserver-utils \
        libxkbcommon-x11-0 && \
# Install Zoom dependencies
    apt-get install --no-install-recommends -y \
        libxcb-xinerama0 \
        libglib2.0-0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-xfixes0 \
        libxcb-randr0 \
        libxcb-image0 \
        libfontconfig1 \
        libgl1-mesa-glx \
        libegl1-mesa \
        libxi6 \
        libsm6 \
        libxrender1 \
        libpulse0 \
        libxcomposite1 \
        libxslt1.1 \
        libsqlite3-0 \
        libxcb-keysyms1 \
        libxcb-xtest0 && \
# Install Zoom (original uses Version 5.13.0 (599)
    #wget -q -O zoom_amd64.deb https://zoom.us/client/latest/zoom_amd64.deb && \
    #wget -q -O zoom_amd64.deb https://zoom.us/client/5.13.0.599/zoom_amd64.deb && \
    wget -q -O zoom_amd64.deb https://zoom.us/client/5.13.4.711/zoom_amd64.deb && \
    #wget -q -O zoom_amd64.deb hhttps://cdn.zoom.us/prod/5.13.4.711/zoom_amd64.deb && \
    dpkg -i zoom_amd64.deb && \
    apt-get -f install -y && \
    rm -rf zoom_amd64.deb && \
# Install support for Intel GPU hardware accelerators VA-API for ffmpeg encoding
    apt-get install --no-install-recommends -y \
        intel-media-va-driver \
        i965-va-driver \
        mesa-va-drivers \
        vainfo && \
# Install support for NVIDIA GPU hardware accelerators NVENC for ffmpeg encoding
    apt-get install --no-install-recommends -y \
        nvidia-driver-525 && \
# resolve redirected meeting URLs
    apt-get install --no-install-recommends -y \
        curl && \
# debugging tools ( to be removed)
    apt-get install --no-install-recommends -y \
        less && \
# Install FFmpeg 
    apt-get install --no-install-recommends -y \
        ffmpeg \
        libavcodec-extra && \
# Install Python dependencies for script
    apt-get install --no-install-recommends -y \
        python3 \
        python3-pip \
        python3-tk \
        python3-dev \
        python3-setuptools \
        scrot && \
    pip3 install --upgrade --no-cache-dir -r ${HOME}/res/requirements.txt && \
# Install VLC - optional
    apt-get install --no-install-recommends -y vlc && \
# install samba server
    apt-get install --no-install-recommends -y \
    samba \
    samba-common-bin \
    acl && \
# Clean up
    apt-get autoremove --purge -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# Allow access to pulseaudio
RUN adduser zoomrec pulse-access

# Allow access to intel VAAPI hardware acceleration
# RUN groupadd -g 110 render # for intel
RUN adduser zoomrec render
RUN adduser zoomrec video

USER zoomrec

# Add home resources
ADD res/home/ ${HOME}/

# Add startup
ADD res/entrypoint.sh ${START_DIR}/entrypoint.sh
ADD res/starting.sh ${START_DIR}/starting.sh
ADD res/xfce.sh ${START_DIR}/xfce.sh

# Add python script with resources
ADD zoomrec.py ${HOME}/
ADD telegram_bot.py ${HOME}/
ADD imap_bot.py ${HOME}/
ADD events.py ${HOME}/
ADD res/img ${HOME}/img

# Set permissions
USER 0
RUN chmod a+x ${START_DIR}/entrypoint.sh && \
    chmod a+x ${START_DIR}/starting.sh && \
    chmod -R a+rw ${START_DIR} && \
    chown -R zoomrec:zoomrec ${HOME} && \
    find ${HOME}/ -name '*.sh' -exec chmod -v a+x {} + && \
    find ${HOME}/ -name '*.desktop' -exec chmod -v a+x {} +

# samba server setup
COPY res/smb.conf /etc/samba/smb.conf
RUN useradd $SAMBA_USER
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN echo -ne "$SAMBA_PASS\n$SAMBA_PASS\n" | smbpasswd -a -s $SAMBA_USER && \
    groupadd samba && \
    gpasswd -a $SAMBA_USER samba && \
    testparm -s 
# samba ports
EXPOSE 139 445 137 138
EXPOSE ${VNC_PORT}

CMD ${START_DIR}/entrypoint.sh