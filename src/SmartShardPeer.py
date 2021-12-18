import requests

from src.api import create_app
from src.api.constants import PBFT_INSTANCES, QUORUMS, NEIGHBOURS, API_IP, PORT, DOCKER_IP, QUORUM_ID
import logging
import logging.handlers
import multiprocessing as mp
import os
import time
import json

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

    def __init__(self, inter=None, port=DEFAULT_PORT):
        self.port = port
        self.inter = inter
        self.app = None

    def __del__(self):
        del self.inter
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
        self.app.api = create_app(self.inter)
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

    def peer_port(self):
        return self.port

    def check_neighbors(self, port):
        url = "http://localhost:{port}/quoruminfo".format(port=port)
        recv_neighbors = json.loads(requests.post(url, json={}).text)["neighbors"]
        self.app.api.config[QUORUMS] = recv_neighbors

    # Leave the network cooperatively
    def leave(self):
        logging.info("API peer on port :" + str(self.port) + " attempting to cooperatively leave.")
        self.check_neighbors(self.port)
        quorums = self.app.api.config[QUORUMS]
        quorum_ids = list(quorums.keys())

        inter = self.app.api.config[PBFT_INSTANCES]
        instance_a = inter.instance_a
        instance_b = inter.instance_b
        id_a = inter.committee_id_a
        id_b = inter.committee_id_b
        val_key_a = inter.val_key(id_a)
        val_key_b = inter.val_key(id_b)

        a_leave_success = instance_a.leave_network(val_key_a)
        b_leave_success = instance_b.leave_network(val_key_b)

        if a_leave_success and b_leave_success:
            # Remove self from network
            self.app.terminate()
            self.app.join()
        else:
            if not a_leave_success:
                logging.error(("{}: SmartShard API on " + instance_a.ip() + " was unable to cooperatively leave committee " + str(id_a) + " - rejoining.").format(instance_a.ip()))
                instance_a.rejoin_network()
            if not b_leave_success:
                logging.error(("{}: SmartShard API on " + instance_b.ip() + " was unable to cooperatively leave committee " + str(id_b) + " - rejoining.").format(instance_b.ip()))
                instance_b.rejoin_network()
            return False

        
        try:
            iter(quorums)
        except:
            logging.error(("{}: SmartShard API on " + instance_a.ip() + " was unable to cooperatively leave committee " + str(id_a) + " - rejoining.").format(instance_a.ip()))
            instance_a.rejoin_network()
            logging.error(("{}: SmartShard API on " + instance_b.ip() + " was unable to cooperatively leave committee " + str(id_b) + " - rejoining.").format(instance_b.ip()))
            instance_b.rejoin_network()
            return False

        # Notify neighbors to remove this peer
        for committee_id in quorums:
            for neighbor in quorums[committee_id]:
                neighbor_ip = neighbor[API_IP]
                neighbor_port = neighbor[PORT]
                neighbor_quorum = neighbor[QUORUM_ID]

                url = "http://{address}:{port}/remove/{remove_port}".format(remove_port=self.port,
                                                                          address=neighbor_ip, port=neighbor_port)
                attempts = 0

                # Handle connection refusals due to heavy network traffic
                while attempts < 5:
                    attempts += 1
                    try:
                        requests.post(url, json={})
                    except requests.exceptions.ConnectionError:
                        logging.error("SmartShardPeer PID " + str(self.pid()) + ", port " + str(self.port) + " - co-op leave notif connection refused by peer " + neighbor_ip + str(neighbor_port) + ".")
                        logging.info("SmartShardPeer PID " + str(self.pid()) + ", port " + str(self.port) + " waiting for 5 seconds to retry...")
                        time.sleep(5)
                        continue

                    break

                if attempts > 5:
                    return False

        logging.info(("PID " + str(self.pid()) + " on port:" + str(self.port) + " - successful co-op leave."))
        return True