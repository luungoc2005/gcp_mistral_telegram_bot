import os
import flask
import flask.typing
import json

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

@functions_framework.http
def telegram_webhook(request: flask.Request) -> flask.typing.ResponseReturnValue:
    publisher.publish(topic_name, request.data)
    return "ok"

@functions_framework.cloud_event
def handle_message(cloud_event: functions_framework.CloudEvent):
    event_data_str = str(cloud_event.get_data(), 'utf-8')
    update = telegram.Update.de_json(json.loads(event_data_str), bot)
    chat_id = update.message.chat.id
    # Reply with the same message
    bot.sendMessage(chat_id=chat_id, text=update.message.text) 