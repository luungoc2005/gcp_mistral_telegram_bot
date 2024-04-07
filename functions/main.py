import os
import flask
import flask.typing
import json
import tempfile
import base64
import asyncio
import logging
import multiprocessing
from typing import List
from collections import namedtuple

import llama_cpp
import telegram

import functions_framework
import google.cloud.logging
from google.cloud import pubsub_v1, datastore, storage

from prompt import get_prompt_messages
from chatformat import format_chat_prompt, ChatMessage

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_CLOUD_PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
GOOGLE_CLOUD_PUBSUB_TOPIC_NAME = os.getenv('PUBSUB_TOPIC_NAME')
GOOGLE_CLOUD_STORAGE_BUCKET = os.getenv('BUCKET_NAME')
MODEL = os.getenv('MODEL')

topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=GOOGLE_CLOUD_PROJECT_ID,
    topic=GOOGLE_CLOUD_PUBSUB_TOPIC_NAME,  # Set this to something appropriate.
)
bot = telegram.Bot(token=TELEGRAM_TOKEN)
publisher = pubsub_v1.PublisherClient()
datastore_client = datastore.Client()
storage_client = storage.Client()
logging_client = google.cloud.logging.Client()
bucket = storage_client.get_bucket(GOOGLE_CLOUD_STORAGE_BUCKET)

logging_client.setup_logging()

LlmModel = namedtuple("LlmModel", ["model", "name"])
llama_model: LlmModel = None

event_loop = asyncio.new_event_loop()
asyncio.set_event_loop(event_loop)

@functions_framework.http
def telegram_webhook(request: flask.Request) -> flask.typing.ResponseReturnValue:
    publisher.publish(topic_name, request.data)
    return "ok"

@functions_framework.cloud_event
def handle_message(cloud_event: functions_framework.CloudEvent):
    if event_loop.is_running():
        logging.info("There's a message pending. Waiting for it to finish.")
        while event_loop.is_running():
            pass
    event_loop.run_until_complete(async_handle_message(cloud_event))
    return "ok"

def load_model():
    global llama_model
    if llama_model is not None and llama_model.name == MODEL:
        return llama_model
    # Download the model from GCS if there's a change or first time initialization
    blob = bucket.blob(MODEL)
    with tempfile.NamedTemporaryFile(suffix=".gguf") as temp:
        logging.info(f"Downloading model {MODEL} from GCS to {temp.name}")
        blob.download_to_filename(temp.name)
        logging.info(f"Download completed. Loading model {temp.name}")
        llama_model = LlmModel(
            model=llama_cpp.Llama(temp.name, 
                                  n_ctx=4096,
                                  n_threads=multiprocessing.cpu_count()), 
            name=MODEL
        )
        logging.info(f"Model {MODEL} loaded")
    return llama_model

async def start_handler(messages, update) -> List[str]:
    return [messages[-1].content]

async def default_handler(messages, update) -> List[str]:
    user_message = update.message.text
    messages.append(ChatMessage(role='user', content=user_message))
    prompt, prompt_stop = format_chat_prompt('chatml', messages)
    stop_words = ["<|im_end|>"]
    if prompt_stop is not None:
        stop_words.append(prompt_stop)
    resp = llama_model.model(
        prompt, 
        max_tokens=128,
        temperature=.8,
        min_p=.05,
        top_p=.95,
        repeat_penalty=1.1,
        top_k=40,
        stop=stop_words
    )["choices"][0]["text"]
    return [resp]

handlers = {
    "/start": start_handler,
    "": default_handler,
}

async def async_handle_message(cloud_event: functions_framework.CloudEvent):
    llama_model = load_model()
    event_data_str = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    update = telegram.Update.de_json(json.loads(event_data_str), bot)
    chat_id = update.message.chat.id
    # Reply with the same message
    user_message = update.message.text
    user_name = update.message.chat.first_name
    messages = get_prompt_messages(user_name)

    for k, v in handlers.items():
        if user_message.startswith(k):
            system_replies = await v(messages, update)
            break
    
    for system_reply in system_replies:
        logging.info(f"Generated reply: {system_reply}")
        resp = await bot.sendMessage(chat_id=chat_id, text=system_reply)
        logging.info(f"Sent message to chat_id: {chat_id}, message: {update.message.text}, resp: {resp}")

    return "ok"