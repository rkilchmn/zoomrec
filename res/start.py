import subprocess
import os
import logging
import psutil
import time

BASE_PATH = os.getenv('HOME')

def find_process_id_by_name(process_name):
    list_of_process_objects = []
    # Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
            # Check if process name contains the given name string.
            if process_name.lower() in pinfo['name'].lower():
                list_of_process_objects.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return list_of_process_objects

confno = "89507147174"
pwd = "Q1VBb2RTQ05sVnVBSU5PSTBVVWVJZz09"
# note: in shell '&' char needs to be escaped as '\&'
url = f"zoommtg://zoom.us/join?action=join\&confno={confno}\&pwd={pwd}"

# open the Zoom application
#zoom = subprocess.Popen(f'{BASE_PATH}/zoom.sh {confno} {pwd}', stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
# zoom = subprocess.Popen(f'zoom --url={url}', stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)
subprocess.call(["/usr/bin/open", "/Applications/zoom.us.app"])

# Wait while zoom process is there
list_of_process_ids = find_process_id_by_name('zoom')
while len(list_of_process_ids) <= 0:
    logging.info("No Running Zoom Process found!")
    list_of_process_ids = find_process_id_by_name('zoom')
    time.sleep(1)

print("Zoom started!")
time.sleep(10000)

#     if not join_by_url:
#         # Start Zoom
#         zoom = subprocess.Popen(f'zoom', stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

#         img_name = 'join_meeting.png'
#     else:
#         match = re.search(r"\D+(\d+)\?pwd=(\S+)", meet_id)
#         if match:
#             confno = match.group(0)
#             pwd = match.group(1)
#             # note: in shell '&' char needs to be escaped as '\&'
#             url = f"zoommtg://zoom.us/join?action=join\&confno={confno}\&pwd={pwd}"

#             logging.info(f"Starting zoom with url")
#             zoom = subprocess.Popen(f'zoom --url={url}', stdout=subprocess.PIPE, shell=True, preexec_fn=os.setsid)

#             img_name = 'join.png'
#         else:
#             logging.info(f"Could not extract confno and/or pwd from meeting link:{meet_id}")
    





