import os
import flask
import flask.typing
import json
import logging
import base64
import asyncio

import llama_cpp
import telegram

import functions_framework
from google.cloud import pubsub_v1, datastore

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CLOUD_PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
PUBSUB_TOPIC_NAME = os.getenv('PUBSUB_TOPIC_NAME')

topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=GOOGLE_CLOUD_PROJECT_ID,
    topic=PUBSUB_TOPIC_NAME,  # Set this to something appropriate.
)
bot = telegram.Bot(token=TELEGRAM_TOKEN)
publisher = pubsub_v1.PublisherClient()
datastore_client = datastore.Client()

event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)

@functions_framework.http
def telegram_webhook(request: flask.Request) -> flask.typing.ResponseReturnValue:
    publisher.publish(topic_name, request.data)
    return "ok"

@functions_framework.cloud_event
def handle_message(cloud_event: functions_framework.CloudEvent):
    event_loop.run_until_complete(async_handle_message(cloud_event))
    return "ok"

async def async_handle_message(cloud_event: functions_framework.CloudEvent):
    event_data_str = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    update = telegram.Update.de_json(json.loads(event_data_str), bot)
    chat_id = update.message.chat.id
    # Reply with the same message
    resp = await bot.sendMessage(chat_id=chat_id, text=update.message.text)
    logging.info(f"Sent message to chat_id: {chat_id}, message: {update.message.text}, resp: {resp}")
    return "ok"