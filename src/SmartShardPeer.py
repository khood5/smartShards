import requests

from src.Intersection import Intersection
from src.SawtoothPBFT import SawtoothContainer
from src.api import create_app
from src.api.api_util import get_plain_text
from src.api.constants import PBFT_INSTANCES, QUORUMS, NEIGHBOURS, API_IP, PORT, DOCKER_IP, QUORUM_ID
import logging
import logging.handlers
import multiprocessing as mp
import os
import json
import random

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
smart_shard_peer_log = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def smart_shard_peer_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    smart_shard_peer_log.propagate = console_logging
    smart_shard_peer_log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    smart_shard_peer_log.addHandler(handler)


DEFAULT_PORT = 5000


class SmartShardPeer:

    def __init__(self, peer=None, port=DEFAULT_PORT):
        self.port = port
        self.peer = peer
        self.app = None

    def __del__(self):
        del self.peer
        self.app.terminate()
        self.app.join()  # wait for app kill to fully complete
        del self.app
        smart_shard_peer_log.info('terminating API on {}'.format(self.port))
        del self.port

    def start(self):
        if self.port is None:
            smart_shard_peer_log.error('start called with no PORT')
        if self.app is not None:
            smart_shard_peer_log.error('app on {} is already running'.format(self.port))
        self.app = mp.Process()
        self.app.api = create_app(self.peer)
        temp = self.app.api
        self.app = mp.Process(target=self.app.api.run, kwargs=({'port': self.port}))
        self.app.api = temp
        self.app.daemon = True  # run the api as daemon so it terminates with the peer process process

        self.app.start()
        

    def pid(self):
        return self.app.pid

    def committee_id_a(self):
        return self.app.api.config[PBFT_INSTANCES].committee_id_a

    def committee_id_b(self):
        return self.app.api.config[PBFT_INSTANCES].committee_id_b

    def port(self):
        return self.port

    # Leave the network cooperatively
    def leave(self, notify_peers):
        quorums = [self.committee_id_a(), self.committee_id_b()]
        print("API peer on port :" + str(self.port) + " cooperatively leaving the network, member of quorums " + str(quorums[0]) + ", " + str(quorums[1]))

        # Notify neighbors
        for port in list(notify_peers.keys()):
            for committee in quorums:
                if port != self.port:
                    url = "http://localhost:{port}/remove/{quorum}".format(port=port, quorum=committee)
                    requests.post(url, json={'NODE': str(committee)})

        # Remove self from network
        self.app.terminate()
        self.app.join()
        del notify_peers[self.port]

        # Return the new state of the network
        return notify_peers
