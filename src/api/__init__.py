from flask import Flask
from src.api.routes import add_routes
from src.api.constants import SECRET, PBFT_INSTANCES, DOCKER_NETWORK, QUORUMS, PENDING_PEERS, ACCEPTED_PEERS, FINALIZED_PEERS
from src.SawtoothPBFT import DEFAULT_DOCKER_NETWORK


def create_app(instances=None):
    new_app = Flask(__name__)
    new_app.config[PBFT_INSTANCES] = instances  # holds the instances
    new_app.config[DOCKER_NETWORK] = DEFAULT_DOCKER_NETWORK  # stores the network instances are working on

    # stores the list of neighbours and the quorums they are intersecting
    # API_IP: address of the other host
    # DOCKER_IP: ip of the sawtooth container in this quorum (in the ex quorum a)
    # PORT_KEY: port that the API is hosted on (i.e. the url for the host is http://API_IP:PORT )
    # QUORUM_ID: other quorum that can be reached by this API (in the ex quorum A can reach B via 192.168.1.1:8080)
    # ex: {'a':[{API_IP:192.168.1.1, PORT_KEY:8080, QUORUM_ID:'b'},{IP_ADDRESS:192.168.1.2 ...
    new_app.config[QUORUMS] = {}
    new_app.config[PENDING_PEERS] = {}
    new_app.config[ACCEPTED_PEERS] = {}
    new_app.config[FINALIZED_PEERS] = {}

    add_routes(new_app)

    return new_app


if __name__ == '__main__':
    app = create_app()
    app.run()

