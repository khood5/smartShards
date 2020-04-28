from flask import Flask
from flask_wtf.csrf import CsrfProtect
from src.Peer import Peer
from src.SawtoothPBFT import SawtoothContainer
import os

# app variables
app = Flask(__name__)
csrf = CsrfProtect()
csrf.init_app(app)

# flask requers that we make a CSRF key for use on forms (ex: settings)
# this make a random key when the app starts.
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY

# Sawtooth PBFT instance variables
my_peer = Peer()
singlePeer = SawtoothContainer()

from src.api import routes



