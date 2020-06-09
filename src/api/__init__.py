from flask import Flask
from src.api.routes import add_routes
from src.api.constants import SECRET, PEER, DOCKER_NETWORK, QUORUMS
from src.SawtoothPBFT import DEFAULT_DOCKER_NETWORK


def create_app():
    new_app = Flask(__name__)
    new_app.config[PEER] = None  # holds the instances
    new_app.config[DOCKER_NETWORK] = DEFAULT_DOCKER_NETWORK  # stores the network instances are working on

    # stores the list of quorums and the neighbours in each by ip and port
    # ex: {'a':[{IP_ADDRESS:192.168.1.1, PORT_KEY:8080, QUORUM_ID:'b'},{IP_ADDRESS:192.168.1.2, PORT_KEY:5000...]}
    # i.e  quorum id to list of neighbours and their ip, port and intersecting quorum
    new_app.config[QUORUMS] = {}

    add_routes(new_app)

    return new_app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

from src.api import routes
