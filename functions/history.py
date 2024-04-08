from google.cloud import firestore
from chatformat import ChatMessage
from typing import List
from datetime import datetime
import telegram

firestore_client = firestore.Client()

def append_history(update: telegram.Update, system_reply: str, **kwargs):
    collection = firestore_client.collection(str(update.message.chat_id))
    doc_ref = collection.document(str(update.message.id))
    doc_ref.set({
        "user": update.message.chat.full_name,
        "is_bot": False,
        "message": update.message.text,
        "timestamp": update.message.date.timestamp(),
    })

    reply_doc_ref = collection.document(f"{update.message.id}_reply")
    reply_doc_ref.set({
        "user": "assistant",
        "is_bot": True,
        "message": system_reply,
        "timestamp": datetime.now().timestamp(),
        **kwargs,
    })

def get_history(prompt_history: List[ChatMessage], update: telegram.Update) -> List[ChatMessage]:
    collection = firestore_client.collection(str(update.message.chat_id))
    docs = collection.stream()
    messages = []
    prev_doc = None
    for doc in docs:
        data = doc.to_dict()
        # if the user sends /start, clear the chat history for the turn
        if prev_doc is not None and not prev_doc["is_bot"] and prev_doc["message"] == "/start":
            messages = []
        else:
            role = "assistant" if data["is_bot"] else "user"
            messages.append(ChatMessage(role=role, content=data["message"]))
        prev_doc = data
    history = prompt_history.copy()
    history.extend(messages)
    return history