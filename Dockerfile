FROM ubuntu:24.04

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

# Install basic dependencies
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        apt \
        apt-utils \
        ca-certificates \
        publicsuffix \
        libapt-pkg6.0 \
        libpsl5 \
        libssl3 \
        libnss3 \
        openssl \
        wget \
        locales \
        bzip2 \
        tzdata && \
    locale-gen en_US.UTF-8

# Install TigerVNC
RUN wget -q -O tigervnc-1.10.0.x86_64.tar.gz https://sourceforge.net/projects/tigervnc/files/stable/1.10.0/tigervnc-1.10.0.x86_64.tar.gz && \
    tar xz -f tigervnc-1.10.0.x86_64.tar.gz --strip 1 -C / && \
    rm -rf tigervnc-1.10.0.x86_64.tar.gz

# Install XFCE and other UI components
RUN apt-get install --no-install-recommends -y \
        supervisor \
        xfce4 \
        xfce4-goodies \
        xfce4-pulseaudio-plugin \
        xfce4-terminal \
        xubuntu-icon-theme

# Install audio utilities
RUN apt-get install --no-install-recommends -y \
        pulseaudio \
        pavucontrol

# Install input and X11 utilities
RUN apt-get install --no-install-recommends -y \
        ibus \
        dbus-user-session \
        dbus-x11 \
        dbus \
        at-spi2-core \
        xauth \
        x11-xserver-utils \
        libxkbcommon-x11-0

# Install X11 and multimedia libraries
RUN apt-get install --no-install-recommends -y \
        libxcb-xinerama0 \
        libglib2.0-0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-xfixes0 \
        libxcb-randr0 \
        libxcb-image0 \
        libfontconfig1 \
        # libgl1-mesa-glx \
        # libegl1-mesa \
        libatomic1 \
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
    apt-get install --no-install-recommends -y \
        libqt5x11extras5

# Install Zoom
# Release notes: https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0068973
# Zoom Software Quarterly Lifecycle Policy: https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0061130
# Version 5.16.6(382) valid until August 3, 2024
# wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/5.16.6.382/zoom_amd64.deb \
# RUN wget -q -O zoom_amd64.deb https://zoom.us/client/latest/zoom_amd64.deb && \
# RUN wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/6.2.6.2503/zoom_amd64.deb && \
# wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/5.17.11.3835/zoom_amd64.deb && \
RUN apt-get update && \
    wget -q -O zoom_amd64.deb https://cdn.zoom.us/prod/5.17.11.3835/zoom_amd64.deb && \
    dpkg -i zoom_amd64.deb && \
    apt-get -f install -y && \
    rm -rf zoom_amd64.deb

# Install other utilities
RUN apt-get install --no-install-recommends -y \
        curl \
        less \
        ffmpeg \
        libavcodec-extra \
        python3 \
        python3-pip \
        python3-tk \
        python3-dev \
        python3-setuptools \
        scrot \
        gnome-screenshot

# required python module
RUN pip3 install --upgrade  --break-system-packages --no-cache-dir -r ${HOME}/res/requirements.txt --default-timeout=100
#    pip3 uninstall --yes opencv-python && \
#    pip3 install opencv-python-headless

# work around error in Python 3.7: AttributeError: type object 'Callable' has no attribute '_abc_registry'
RUN if pip3 show typing > /dev/null 2>&1; then pip3 uninstall -y --break-system-packages typing; fi

# samba servr
RUN apt-get install --no-install-recommends -y \
        samba \
        samba-common-bin \
        acl

# Clean up APT when done.
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the noninteractive environment variable to suppress prompts
ENV DEBIAN_FRONTEND=noninteractive

# ENV LIBVA_TRACE=${HOME}/recordings/screenshots/libva_trace.log
# Install support for VA-API GPU hardware accelerators used by ffmpeg encoders
RUN if [ "$GPU_BUILD" = "VAAPI" ]; then \
        # add repoisitory for latest mesa drivers
        # apt update && apt-get install -y software-properties-common && \
        # add-apt-repository ppa:kisak/kisak-mesa && \
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
        apt update && apt-get install -y software-properties-common && \
        apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu/ jammy main restricted universe multiverse" && \
        apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu/ jammy-updates main restricted universe multiverse" && \
        apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu/ jammy-security main restricted universe multiverse" && \
        apt-add-repository -y "deb http://archive.ubuntu.com/ubuntu/ jammy-backports main restricted universe multiverse" && \
        apt-get update && \
        apt-get install -y mesa-va-drivers=23.2.1-1ubuntu3.1~22.04.3 && \
        apt-get install --no-install-recommends -y \
            # standard drivers includes 
            # "radeonsi" for RX4x0/RC5x0
            # " " for IrisXE under WSL2
            vainfo && \
            # "i965" Ivy bridge like HD4000
            # i965-va-driver-shaders && \
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
#         apt-get update && \
#         adduser zoomrec video ; \
#     fi

# Install support for NVIDIA GPU hardware accelerators NVENC for ffmpeg encoding
ENV NVIDIA_DRIVER_CAPABILITIES=video
ENV NVIDIA_VISIBLE_DEVICES=all
RUN if [ "$GPU_BUILD" = "NVIDIA" ] ; then \
        # add repo
	apt-get update && \
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
ADD events.py ${HOME}/
ADD events_api.py ${HOME}/
ADD users.py ${HOME}/
ADD msg_telegram.py ${HOME}/
ADD constants.py ${HOME}/
ADD res/img ${HOME}/img

# posprocessing scripts
ADD res/postprocess.sh ${HOME}/
ADD res/transcribe_video.sh ${HOME}/

# required by pyautogui 
ADD res/.Xauthority ${HOME}/

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