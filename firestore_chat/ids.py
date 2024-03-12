create_room = "create-room"
user_name = "user-name"
join = "join-room"
signout = "sign-out"
message = "message"
send = "send-message"
message_list = "message-list"
scroll_trigger = "scroll-trigger"
msg_range = "message-range"
room_socket = "room-socket-io"
connected_count = "connected-count"
home_dummy = "home-dummy"


def load_more(idx):
    return {"type": "load-more", "idx": idx}


def socket(url):
    return {"type": "socket", "url": url}
