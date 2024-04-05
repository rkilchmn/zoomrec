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

# build container for specific GPU 
ARG GPU_BUILD=""
# group id for the 'render' group (used for VAAPI)
ARG RENDER_GROUPID="" 

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
        libxcb-xtest0 \
        libxcb-cursor0 && \
# WSL2
apt-get install --no-install-recommends -y \
        libxcb-xinerama0 \
        libqt5x11extras5 && \

# Install Zoom (original uses Version 5.13.0 (599)
    #wget -q -O zoom_amd64.deb https://zoom.us/client/latest/zoom_amd64.deb && \
    #wget -q -O zoom_amd64.deb https://zoom.us/client/5.13.0.599/zoom_amd64.deb && \
    #wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/5.13.5.363/zoom_amd64.deb && \
    #wget -q -O zoom_amd64.deb hhttps://cdn.zoom.us/prod/5.13.4.711/zoom_amd64.deb && \
    wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/5.14.5.2430/zoom_amd64.deb && \
    dpkg -i zoom_amd64.deb && \
    apt-get -f install -y && \
    rm -rf zoom_amd64.deb && \
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
        scrot \
        gnome-screenshot && \
    pip3 install --upgrade --no-cache-dir -r ${HOME}/res/requirements.txt && \
    pip3 uninstall --yes opencv-python && \ 
    pip3 install opencv-python-headless && \ 
# Install VLC - optional
   apt-get install --no-install-recommends -y vlc && \
# install samba server
    apt-get install --no-install-recommends -y \
    samba \
    samba-common-bin \
    acl

ENV LIBVA_TRACE=${HOME}/recordings/screenshots/libva_trace.log
# Install support for VA-API GPU hardware accelerators used by ffmpeg encoders
RUN if [ "$GPU_BUILD" = "VAAPI" ]; then \
        # add repoisitory for latest mesa drivers
        apt-get install -y software-properties-common && \
        add-apt-repository ppa:kisak/kisak-mesa && \

        # add intel non-free repositories
        # apt-get install -y gnupg && \
        # curl -fsSL https://repositories.intel.com/graphics/intel-graphics.key | apt-key add - > /dev/null && \
        # echo "deb [trusted=yes arch=amd64] https://repositories.intel.com/graphics/ubuntu focal main" > /etc/apt/sources.list.d/intel-graphics.list  && \
        # apt-get update && \
        # add intel packages https://www.intel.com/content/www/us/en/docs/oneapi/installation-guide-linux/2023-1/configure-wsl-2-for-gpu-workflows.html
        # apt-get install --no-install-recommends -y \
        #     vainfo \
        #     clinfo \
        #     intel-opencl-icd intel-level-zero-gpu level-zero \
        #     intel-media-va-driver-non-free libmfx1 libmfxgen1 libvpl2 \
        #     libegl-mesa0 libegl1-mesa libegl1-mesa-dev libgbm1 libgl1-mesa-dev libgl1-mesa-dri \
        #     libglapi-mesa libgles2-mesa-dev libglx-mesa0 libigdgmm12 libxatracker2 mesa-va-drivers \
        #     mesa-vdpau-drivers mesa-vulkan-drivers va-driver-all && \

        # install media drivers for GPU based on  LIBVA_DRIVER_NAME value
        apt-get install --no-install-recommends -y \
            # standard drivers includes 
            # "radeonsi" for RX4x0/RC5x0
            # "d3d12" for IrisXE under WSL2
            mesa-va-drivers \
            # "i965" Ivy bridge like HD4000
            i965-va-driver-shaders && \
            # untested: "iHD" for Broadwell and above Intel iGPUs        

        # va-api related tools for testing
        # apt-get install --no-install-recommends -y \
        #     vainfo \
        #     clinfo && \

        # provide access to devices
        groupadd -g ${RENDER_GROUPID} render && \
        adduser zoomrec render && \
        adduser zoomrec video ; \
    fi
# RUN if [ "$GPU_BUILD" = "AMD" ]; then \
#         apt-get install --no-install-recommends -y \
#             mesa-va-drivers && \
#         groupadd -g ${RENDER_GROUPID} render && \
#         adduser zoomrec render && \
#         adduser zoomrec video ; \
#     fi

# RUN if [ "$GPU_BUILD" = "INTEL" ]; then \
#         apt-get install --no-install-recommends -y \
#             intel-media-va-driver \
#             i965-va-driver && \
#         groupadd -g ${RENDER_GROUPID} render && \
#         adduser zoomrec render && \
#         adduser zoomrec video ; \
#     fi

# Install support for NVIDIA GPU hardware accelerators NVENC for ffmpeg encoding
ENV NVIDIA_DRIVER_CAPABILITIES=video
ENV NVIDIA_VISIBLE_DEVICES all
RUN if [ "$GPU_BUILD" = "NVIDIA" ] ; then \
        # add repo
        apt-get install -y gnupg && \
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && \
        # install
        apt-get update && \
        apt-get install --no-install-recommends -y \
            nvidia-container-runtime ; \
    fi

# Clean up
RUN apt-get autoremove --purge -y && \
    apt-get autoclean -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# Allow access to pulseaudio
RUN adduser zoomrec pulse-access

USER zoomrec

# Add home resources
ADD res/home/ ${HOME}/

# Add startup
ADD res/entrypoint.sh ${START_DIR}/entrypoint.sh
ADD res/starting.sh ${START_DIR}/starting.sh
ADD res/xfce.sh ${START_DIR}/xfce.sh

# Add python script with resources
ADD zoomrec.py ${HOME}/
ADD zoomrec_client.py ${HOME}/
ADD telegram_bot.py ${HOME}/
ADD imap_bot.py ${HOME}/
ADD events.py ${HOME}/
ADD res/img ${HOME}/img

# Set permissions 
USER root
RUN chown -R zoomrec:zoomrec ${HOME} && \
    chmod a+x ${START_DIR}/entrypoint.sh && \
    chmod a+x ${START_DIR}/starting.sh && \
    chmod a+x ${START_DIR}/xfce.sh && \
    chmod -R a+rw ${START_DIR} && \
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