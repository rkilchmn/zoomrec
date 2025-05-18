import time
import requests
from urllib.parse import quote
import os

# telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_RETRIES = 5

def send_telegram_message( chat_id, text, retries=TELEGRAM_RETRIES):
    url_req = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage" + "?chat_id=" + chat_id + "&text=" + quote(text)
    tries = 0
    success = False
    while not success:
        results = requests.get(url_req)
        results = results.json()
        success = 'ok' in results and results['ok']
        tries+=1
        if not success and tries < retries:
            time.sleep(5)
        if not success and tries >= retries:
            break
    return success
