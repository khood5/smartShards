from flask import Flask
from flask_wtf.csrf import CsrfProtect
from src.Peer import Peer
from src.api.single_peer import SinglePeer
from src.api.routes import add_routes
from src.api.routes import SECRET, PBFT_INSTANCES, DOCKER_NETWORK, NEIGHBOURS
from src.SawtoothPBFT import SawtoothContainer, DEFAULT_DOCKER_NETWORK
import os

# flask requires that we make a CSRF key for use on forms (ex: settings)
# this makes a random key when the app starts.
SECRET_KEY = os.urandom(32)


def create_app():
    new_app = Flask(__name__)
    csrf = CsrfProtect()
    csrf.init_app(new_app)
    new_app.config[SECRET] = SECRET_KEY
    new_app.config[PBFT_INSTANCES] = None  # holds the instances
    new_app.config[DOCKER_NETWORK] = DEFAULT_DOCKER_NETWORK  # stores the network instances are working on

    # stores the list of quorums and the neighbours in each by ip and port
    # ex: 'quorum_a':{IP_ADDRESS_KEY:192.168.1.1, PORT_KEY:8080}
    new_app.config[NEIGHBOURS] = {}

    add_routes(new_app)
    return new_app


if __name__ == '__main__':
    app = create_app()
    app.run()

from src.api import routes
