#!/bin/bash

# from https://github.com/kehindeoderinde/docker-sftp-server
set -Eeo pipefail

# shellcheck disable=2154
trap 's=$?; echo "$0: Error on line "$LINENO": $BASH_COMMAND"; exit $s' ERR

# Extended regular expression (ERE) for arguments
reUser='[A-Za-z0-9._][A-Za-z0-9._-]{0,31}' # POSIX.1-2008
rePass='[^:]{0,255}'
reUid='[[:digit:]]*'
reGid='[[:digit:]]*'
reDir='[^:]*'

function log() {
    echo "[$0] $*"
}

function validateArg() {
    name="$1"
    val="$2"
    re="$3"

    if [[ "$val" =~ ^$re$ ]]; then
        return 0
    else
        log "ERROR: Invalid $name \"$val\", does not match required regex pattern: $re"
        return 1
    fi
}

log "Parsing user data: \"$1\""
IFS=':' read -ra args <<< "$1"

skipIndex=0
chpasswdOptions=""
useraddOptions=(--no-user-group --badname --shell /usr/sbin/nologin --create-home)

user="${args[0]}"; validateArg "username" "$user" "$reUser" || exit 1
pass="${args[1]}"; validateArg "password" "$pass" "$rePass" || exit 1

if [ "${args[2]}" == "e" ]; then
    chpasswdOptions="-e"
    skipIndex=1
fi

uid="${args[$((skipIndex+2))]}"; validateArg "UID" "$uid" "$reUid" || exit 1
gid="${args[$((skipIndex+3))]}"; validateArg "GID" "$gid" "$reGid" || exit 1
dir="${args[$((skipIndex+4))]}"; validateArg "dirs" "$dir" "$reDir" || exit 1

# Check if user already exists
if getent passwd "$user" > /dev/null; then
    log "WARNING: User \"$user\" already exists. Skipping."
    exit 0
fi

if [ -n "$uid" ]; then
    useraddOptions+=(--non-unique --uid "$uid")
fi

if [ -n "$gid" ]; then
    if ! getent group "$gid" > /dev/null; then
        groupadd --gid "$gid" "group_$gid"
    fi
    useraddOptions+=(--gid "$gid")
fi

# Add the user
useradd "${useraddOptions[@]}" "$user"

# Retrieve user ID for chown commands
uid="$(id -u "$user")"

# if gid not supplied use default group for ownership
if [ -z "$gid" ]; then
    $gid="users"
fi

homeDir="/home/${user}"
chrootDir="$2/${user}"

# Ensure the chroot directory exists under the specified homeRoot
if [ ! -d "$chrootDir" ]; then
    log "Creating chroot directory: $chrootDir"
    mkdir -p "$chrootDir"
    chown root:root "$chrootDir"
    chmod 755 "$chrootDir"

    # Generate SSH key pair if chroot directory is newly created
    log "Generating SSH key pair for $user"
    mkdir -p "$chrootDir/.ssh"
    ssh-keygen -t rsa -b 2048 -f "$chrootDir/.ssh/id_rsa" -N ""  # No passphrase
    chown -R "$uid:$gid" "$chrootDir/.ssh"
    chmod 700 "$chrootDir/.ssh"
    chmod 600 "$chrootDir/.ssh/id_rsa"
    chmod 644 "$chrootDir/.ssh/id_rsa.pub"
else
    log "Chroot directory already exists: $chrootDir"
fi

# add public key to ssh authorized_keys
mkdir -p "$homeDir/.ssh"
chmod 700 "$homeDir/.ssh"
userKeysAllowedFile="$homeDir/.ssh/authorized_keys"
cat "$chrootDir/.ssh/id_rsa.pub" >> "$userKeysAllowedFile"
chmod 600 "$userKeysAllowedFile"
chown -R "$uid:$gid" "$homeDir/.ssh"

# Set password if provided, else disable password
if [ -n "$pass" ]; then
    echo "$user:$pass" | chpasswd $chpasswdOptions
else
    usermod -p "*" "$user" # Disable password
fi

# Add SSH keys to authorized_keys with valid permissions
userKeysQueuedDir="$homeDir/.ssh/keys"
if [ -d "$userKeysQueuedDir" ]; then
    userKeysAllowedFileTmp="$(mktemp)"
    userKeysAllowedFile="$homeDir/.ssh/authorized_keys"

    for publickey in "$userKeysQueuedDir"/*; do
        cat "$publickey" >> "$userKeysAllowedFileTmp"
    done

    # Remove duplicate keys
    sort < "$userKeysAllowedFileTmp" | uniq > "$userKeysAllowedFile"

    chown "$uid:$gid" "$userKeysAllowedFile"
    chmod 600 "$userKeysAllowedFile"
fi

# Make sure additional directories exist under the specified home directory
if [ -n "$dir" ]; then
    IFS=',' read -ra dirArgs <<< "$dir"
    for dirPath in "${dirArgs[@]}"; do
        dirPath="$chrootDir/$dirPath"
        if [ ! -d "$dirPath" ]; then
            log "Creating directory: $dirPath"
            mkdir -p "$dirPath"
            chown -R "$uid:$gid" "$dirPath"
            chmod 770 "$dirPath" # allow group rw access
        else
            log "Directory already exists: $dirPath"
        fi
    done
fi
