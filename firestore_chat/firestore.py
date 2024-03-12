import os
from datetime import datetime

from firebase_admin import credentials, firestore, get_app, initialize_app
from flask import session
from google.cloud.firestore_v1 import (
    Client as FirestoreClient,
    CollectionReference,
    DocumentReference,
)

from firestore_chat.server import socketio

os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"

project_id = "demo"

try:
    firestore_app = get_app(name=project_id)

# If no app was found, initialize a new app
except ValueError:
    cred = credentials.ApplicationDefault()
    firestore_app = initialize_app(
        credential=cred,
        options={"projectId": project_id},
        name=project_id,
    )

db: FirestoreClient = firestore.client(firestore_app)


def get_chatroom_doc(room_name: str) -> DocumentReference:
    """Get chatroom document."""
    return db.collection("chats").document(room_name)


def get_message_collection(room_name: str) -> CollectionReference:
    """Get messages collection for a chatroom."""
    return get_chatroom_doc(room_name).collection("messages")


def get_connected_collection(room_name: str) -> CollectionReference:
    """Get connected users collection for a chatroom."""
    return get_chatroom_doc(room_name).collection("connected")


def add_room_connected(room_name: str, user: str):
    """Add connected user to a chatroom."""
    get_connected_collection(room_name).document(user).set(
        {"connected": datetime.utcnow().isoformat()}
    )


def messages_snapshot(room_name: str):
    """Create a snapshot callback to update chat messages."""
    def refresh_messages(_docs, _changes, update_time):
        """Callback to refresh the message list when new messages are added."""
        socketio.emit("newMessage", str(update_time), room=room_name, namespace="/chat")

    return refresh_messages


def connected_snapshot(room_name: str):
    """Create a snapshot callback to update connected users."""
    def refresh_connected(_docs, changes, update_time):
        if not changes:
            return

        socketio.emit(
            "updateConnected",
            {
                "time": str(update_time),
                "user": changes[0].document.id,
                "action": "joined" if changes[0].new_index != -1 else "left",
            },
            room=room_name,
            namespace="/chat",
        )
        return

    return refresh_connected


def post_message(message: str, room_name: str):
    """Post a message to a chatroom."""
    collection = get_message_collection(room_name)
    collection.add(
        {
            "user": session["user"]["email"],
            "text": message,
            "sentAt": datetime.utcnow().isoformat(),
        }
    )


def remove_room_connected(room_name: str, user: str):
    """Remove connected user from a chatroom."""
    get_connected_collection(room_name).document(user).delete()

# Run `gcloud emulators firestore start --host-port=localhost:8080 --project=demo`

__all__ = ["db"]
