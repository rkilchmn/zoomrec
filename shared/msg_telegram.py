import requests
from urllib.parse import quote
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import RequestException
import logging

# telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_RETRIES = 5

@retry(
    stop=stop_after_attempt(TELEGRAM_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type(RequestException),
    reraise=True
)
def send_telegram_message(chat_id, text):
    url_req = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage" + "?chat_id=" + chat_id + "&text=" + quote(text)+"&parse_mode=HTML"
    response = requests.get(url_req)
    response.raise_for_status()
    results = response.json()
    
    if not ('ok' in results and results['ok']):
        raise Exception(f"Telegram API error: {results}")
    
    return True
