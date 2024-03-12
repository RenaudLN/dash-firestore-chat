from flask import Flask
from flask_socketio import SocketIO

server = Flask(__name__)
socketio = SocketIO(server)
