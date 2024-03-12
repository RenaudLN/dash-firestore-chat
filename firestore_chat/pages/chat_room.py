from datetime import datetime

import dash_mantine_components as dmc
from dash import (
    ALL,
    Input,
    Output,
    Patch,
    State,
    callback,
    clientside_callback,
    ctx,
    dcc,
    html,
    no_update,
    register_page,
)
from dash_iconify import DashIconify
from dash_socketio import DashSocketIO
from flask import session, request
from flask_socketio import join_room, leave_room, rooms

from google.cloud.firestore_v1 import FieldFilter

from firestore_chat import ids
from firestore_chat.firestore import (
    add_room_connected,
    connected_snapshot,
    get_message_collection,
    get_connected_collection,
    messages_snapshot,
    post_message,
    remove_room_connected,
)
from firestore_chat.server import server, socketio


register_page(__name__, path_template="/chat/<room_name>")


MSG_UPDATES = {}
MSG_PAGE_SIZE = 20
CONNECTED_UPDATES = {}


def layout(room_name: str = None, socket_ids: list[str] = None):
    """Chat room page layout."""

    if not room_name:
        return dmc.Text("Not found")

    # This shouldn't happen
    if "user" not in session:
        return dmc.Anchor("Go back", href="/")

    session["room_name"] = room_name

    # Wait for the socket to be connected
    if not socket_ids:
        return base_page(
            room_name,
            [dmc.Group(dmc.Loader(), position="center", py="5rem")],
        )

    return base_page(
        room_name,
        [
            dmc.Paper(
                dmc.ScrollArea(
                    dmc.Stack([], id=ids.message_list, spacing="sm", p="1rem"),
                    sx={"flex": 1, "&>div>div": {"height": "100%"}},
                ),
                withBorder=True,
                style={
                    "maxHeight": "calc(100vh - 14rem)",
                    "display": "flex",
                    "flexDirection": "column",
                    "flex": 1,
                },
            ),
            dmc.Textarea(id=ids.message, label="Your message", mb=-10),
            html.Div(dmc.Button("Send", id=ids.send)),
            html.Div(id=ids.scroll_trigger),
            dcc.Store(data={}, id=ids.msg_range),
        ],
    )


def base_page(room_name: str, children: list):
    """Wrapper template for chat room page."""
    return dmc.Container(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Anchor(
                            dmc.ActionIcon(
                                DashIconify(icon="mingcute:arrow-left-fill", height=16),
                                radius="xl",
                            ),
                            href="/",
                        ),
                        dmc.Title(f"Chat room: {room_name}", order=4),
                        dmc.Text(session["user"]["email"], size="xs", ml="auto"),
                        dmc.Text(
                            id=ids.connected_count,
                            size="xs",
                            sx={"&:not(:empty)": {"marginLeft": "-0.25rem"}},
                        ),
                    ],
                    spacing="xs",
                ),
                *children,
                DashSocketIO(
                    url="/chat",
                    id=ids.socket("/chat"),
                    eventNames=["newMessage", "updateConnected"],
                ),
            ],
            style={"height": "100%"},
        ),
        py="1rem",
        sx={"height": "calc(100vh - 2rem)"},
    )


@server.before_request
def watch_messages_and_connected():
    """
    Ensure that a server instance answering a client
    is listening for DB changes on messages and connected users.
    """
    if not request.referrer:
        return
    referrer = request.referrer.removeprefix(request.url_root)
    room_name = session.get("room_name")
    if room_name and referrer == f"chat/{room_name}":
        if room_name not in MSG_UPDATES:
            MSG_UPDATES[room_name] = (
                get_message_collection(room_name)
                .order_by("sentAt", direction="DESCENDING")
                .limit(1)
                .on_snapshot(messages_snapshot(room_name))
            )
        if room_name not in CONNECTED_UPDATES:
            CONNECTED_UPDATES[room_name] = (
                get_connected_collection(room_name)
                .order_by("connected", direction="DESCENDING")
                .on_snapshot(connected_snapshot(room_name))
            )


@socketio.on("connect", namespace="/chat")
def on_chat_connect(data):
    """Make a user join the room when they connect to the socket."""
    room = data["pathname"].removeprefix("/chat/")
    join_room(room)


@socketio.on("disconnect", namespace="/chat")
def on_chat_disconnect():
    """
    Remove user from the room when they disconnect from the socket.
    Also update the connected users in the DB.
    """
    for room in rooms():
        if room == request.sid:
            continue
        leave_room(room)
        remove_room_connected(room, session["user"]["email"])


@callback(
    Output(ids.message_list, "children"),
    Output(ids.scroll_trigger, "data-scroll"),
    Output(ids.msg_range, "data"),
    Input(ids.message_list, "id"),
    Input(ids.socket("/chat"), "data-newMessage"),
    Input(ids.load_more(ALL), "n_clicks"),
    State(ids.msg_range, "data"),
)
def populate_messages(_t1, _t2, t3, msg_range: dict):
    """
    Populate the chat message list.

    This is triggered on 3 inputs:
    - The message list is rendered
    - A new message is added
    - The "load more" button is clicked
    """
    children = []
    collection = get_message_collection(session["room_name"])
    now = datetime.utcnow().isoformat()

    n_messages = 0

    # Base query
    query = collection.order_by("sentAt", direction="ASCENDING")

    # When a new message is added by a user
    if msg_range.get("latest") and ctx.triggered_id == ids.socket("/chat"):
        query = query.where(filter=FieldFilter("sentAt", ">=", msg_range.get("latest")))
    # When the load more button is clicked
    elif ctx.triggered_id == ids.load_more("top"):
        # If button is not clicked, don't update
        if not t3[0]:
            return [no_update] * 3
        query = query.where(
            filter=FieldFilter("sentAt", "<", msg_range.get("earliest"))
        )
        n_messages = query.count().get()[0][0].value
        query = query.limit_to_last(MSG_PAGE_SIZE)
    # When the list renders
    else:
        query = query.limit_to_last(MSG_PAGE_SIZE)
        n_messages = collection.count().get()[0][0].value

    # We only load MSG_PAGE_SIZE messages at a time, adding a "Load more" button if
    # there were previous messages
    if n_messages > MSG_PAGE_SIZE:
        children.append(
            dmc.Group(
                dmc.Button(
                    # NOTE: The id used here is a dict so that the callback may function
                    # with or without the component present on the page. This leverages
                    # the ALL pattern matching in the callback.
                    "Load more", variant="light", compact=True, id=ids.load_more("top")
                ),
                position="center",
                mb="0.5rem",
            )
        )

    earliest = msg_range.get("earliest")

    # Execute the DB query and add Dash component for the messages
    for i, doc in enumerate(query.get()):
        data = doc.to_dict()
        if i == 0 and (ctx.triggered_id != ids.socket("/chat") or earliest is None):
            earliest = data["sentAt"]

        card = dmc.Paper(
            dmc.Text(data["text"]),
            withBorder=True,
            p="0.5rem 1rem",
            mr="6rem",
            sx={
                "position": "relative",
                "background": "transparent",
                "isolation": "isolate",
                "overflow": "hidden",
                "&::before": {
                    "position": "absolute",
                    "content": '""',
                    "inset": 0,
                    "zIndex": -1,
                    "background": "white",
                    "opacity": 0.033,
                },
            },
            className="chat-card",
        )

        # Style the message differently whether it is sent by the user or someone else
        if data["user"] == session["user"]["email"]:
            card.sx["transform"] = "translateX(6rem)"
            card.sx["&::before"]["background"] = "var(--mantine-color-blue-3)"
            children.append(card)
        else:
            card.sx["flex"] = 1
            children.append(
                dmc.Group(
                    [
                        dmc.Tooltip(
                            dmc.Avatar(
                                data["user"][:2].upper(), radius="xl", color="blue"
                            ),
                            label=data["user"],
                        ),
                        card,
                    ],
                    className="chat-card-group",
                )
            )

    # Return the updated message list. We also keep track of:
    # * the earliest message in the list so that we can load more messages if needed
    # * the time at which the latest message was pulled
    # Finally we instruct the message list to scroll
    # * to the bottom if the message list was rendered or a new message was added
    # * to the top if the load more button was clicked
    if children:
        update = Patch()
        if ctx.triggered_id == ids.load_more("top"):
            del update[0]
            for child in children[::-1]:
                update.prepend(child)
            scroll_to = "top"
        else:
            update.extend(children)
            scroll_to = "bottom"
        return update, scroll_to, {"latest": now, "earliest": earliest}

    if msg_range.get("latest"):
        return no_update, no_update, {"latest": now, "earliest": earliest}

    return (
        dmc.Text("No messages yet", color="dimmed", italic=True),
        no_update,
        {"latest": now, "earliest": earliest},
    )


@callback(
    Output(ids.message_list, "data-connected"),
    Input(ids.message_list, "id"),
)
def trigger_add_connected(_):
    """Update the DB with a new connected user once the message list is rendered."""
    add_room_connected(session["room_name"], session["user"]["email"])
    return no_update


@callback(
    Output(ids.message, "value"),
    Input(ids.send, "n_clicks"),
    State(ids.message, "value"),
    prevent_initial_call=True,
)
def send_message(_, message):
    """Send a message to the chat room."""
    if not message:
        return no_update
    room_name = session["room_name"]
    post_message(message, room_name)
    return ""


@callback(
    Output(ids.message_list, "children", allow_duplicate=True),
    Output(ids.scroll_trigger, "data-scroll", allow_duplicate=True),
    Output(ids.connected_count, "children"),
    Input(ids.socket("/chat"), "data-updateConnected"),
    prevent_initial_call=True,
)
def add_joined_left(connection):
    """Add info about users joining and leaving the room."""
    def _text(val):
        return dmc.Text(
            val,
            color="dimmed",
            size="sm",
            italic=True,
            sx={
                ".chat-card+&, .chat-card-group+&, &+.chat-card, &+.chat-card-group": {
                    "marginTop": "0.5rem"
                }
            },
        )

    user = connection["user"]
    action = connection["action"]
    update = Patch()
    if action == "joined":
        if user == session["user"]["email"]:
            update.append(_text("You have joined the chat"))
        else:
            update.append(_text(f"{user} has joined the chat"))
    if action == "left":
        update.append(_text(f"{user} has left the chat"))

    connected_count = (
        get_connected_collection(session["room_name"]).count().get()[0][0].value
    )
    return update, "bottom", f"- {connected_count} connected"


# Scroll to the bottom/top of the message list as required
clientside_callback(
    """(scrollTo, id) => {
        const el = document.getElementById(id).parentNode.parentNode
        el.scrollTop = scrollTo === 'bottom' ? el.scrollHeight : 0
        return dash_clientside.no_update
    }""",
    Output(ids.scroll_trigger, "data-scrolled"),
    Input(ids.scroll_trigger, "data-scroll"),
    State(ids.message_list, "id"),
)
