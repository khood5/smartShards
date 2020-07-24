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

        new_network = {}
        for port in list(notify_peers.keys()):
            if self.port != port:
                new_network[port] = notify_peers[port]

        delete_committee = str(self.committee_id_b())

        gap_closing_peer = None

        # Notify neighbors
        for port in list(new_network.keys()):
            inter = new_network[port].app.api.config[PBFT_INSTANCES]
            if not inter.in_committee(delete_committee):
                continue
            id_a = str(inter.committee_id_a)
            id_b = str(inter.committee_id_b)

            if id_a != "" and id_b != "":
                # Intersection in two quorums - remove the sawtooth container in the leaving intersection

                # Remove committee membership
                url = "http://localhost:{port}/remove/{quorum}".format(port=port, quorum=delete_committee)
                requests.post(url, json={'NODE': str(delete_committee)})

                corresponding_id = None
                if id_a == delete_committee:
                    corresponding_id = id_a
                    new_network[port].app.api.config[PBFT_INSTANCES].committee_id_a = ""
                    #print("Removed committee A " + str(corresponding_id) + " from " + str(port))
                elif id_b == delete_committee:
                    corresponding_id = id_b
                    new_network[port].app.api.config[PBFT_INSTANCES].committee_id_b = ""
                    #print("Removed committee B " + str(corresponding_id) + " from " + str(port))

                # Search neighbors for another peer only participating in 1 quorum
                # If found, make a new quorum with them
                for search_port in list(new_network.keys()):
                    if search_port != port:
                        search_inter = new_network[search_port].app.api.config[PBFT_INSTANCES]
                        search_committee_a = search_inter.committee_id_a
                        search_committee_b = search_inter.committee_id_b
                        if search_committee_a != "" and search_committee_b == "":
                            if gap_closing_peer is None:
                                gap_closing_peer = new_network[port]
                                #print("Peer on port " + str(search_port) + " closing gap.")

                                new_sawtooth = SawtoothContainer()
                                new_inter = Intersection(inter._Intersection__instance_a, new_sawtooth, id_a,
                                                         corresponding_id)

                                ips_a = []
                                vals_a = []
                                users_a = []

                                ips_b = []
                                vals_b = []
                                users_b = []

                                new_sawtooth = SawtoothContainer()
                                new_inter = Intersection(inter._Intersection__instance_a, new_sawtooth, id_a,
                                                         corresponding_id)

                                for port in list(new_network.keys()):
                                    replace_inter = new_network[port].app.api.config[PBFT_INSTANCES]
                                    ips_a.append(replace_inter._Intersection__instance_a.ip())
                                    vals_a.append(replace_inter._Intersection__instance_a.val_key())
                                    users_a.append(replace_inter._Intersection__instance_a.user_key())

                                    ips_b.append(replace_inter._Intersection__instance_b.ip())
                                    vals_b.append(replace_inter._Intersection__instance_b.val_key())
                                    users_b.append(replace_inter._Intersection__instance_b.user_key())

                                new_sawtooth.join_sawtooth(ips_b)

                                new_inter.peer_join(id_a, ips_a)
                                new_inter.update_committee(vals_a, users_a, True)

                                new_inter.peer_join(corresponding_id, ips_b)
                                new_inter.update_committee(vals_b, users_b, True)

                                # del inter._Intersection__instance_b
                                inter = new_inter
                            else:
                                print("") # do stuff

            # Other peer will no longer participate in any quorums, they should terminate
            elif id_a != "" and id_b == "":
                new_network[port].leave(new_network)
            elif id_a == "" and id_b != "":
                new_network[port].leave(new_network)

        # Remove self from network
        self.app.terminate()
        self.app.join()
        del notify_peers[self.port]

        # Return the new state of the network
        return new_network
