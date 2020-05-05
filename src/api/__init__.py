from flask import Flask
from flask_wtf.csrf import CsrfProtect
from src.Peer import Peer
from src.api.single_peer import SinglePeer
import os

# app variables
APP = Flask(__name__)
csrf = CsrfProtect()
csrf.init_app(APP)

# flask requers that we make a CSRF key for use on forms (ex: settings)
# this make a random key when the app starts.
SECRET_KEY = os.urandom(32)
APP.config['SECRET_KEY'] = SECRET_KEY

# Sawtooth PBFT instance variables
PBFT_PEER = Peer()

SINGLE_PEER = SinglePeer('bridge')

from src.api import routes



