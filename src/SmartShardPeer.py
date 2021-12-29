import requests

from src.api import create_app
from src.api.constants import PBFT_INSTANCES, QUORUMS, NEIGHBOURS, API_IP, PORT, DOCKER_IP, QUORUM_ID
import logging
import logging.handlers
import multiprocessing as mp
import os
import time
import json
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection

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
    
    def join_network(self, known_host):
        res = requests.get(f"http://{known_host}/min+intersection").json()
        print(f"peer on port {self.port} knows min intersection")
        print(res)
        min_intersection = res["min_intersection"]
        min_intersection_peers = list(res["peers"].keys())
        min_peer = min_intersection_peers[0]
        min_peer_ip = min_peer.split(':')[0]
        min_peer_port = min_peer.split(':')[1]

        id_a = min_intersection[0]
        id_b = min_intersection[1]

        if len(min_intersection_peers) == 0:
            logging.error(f"The minimum intersection has no peers, can't ask for neighbors")
            return
        
        a = SawtoothContainer()
        print(f"peer a has IP: {a.ip()}")
        b = SawtoothContainer()
        print(f"peer b has IP: {b.ip()}")
        self.inter = Intersection(a, b, id_a, id_b)
        
        if self.app is None:
            logging.info(f"SmartShardPeer on port {self.port} does not have an app yet, starting it now")
            self.start()

        min_intersection_neighbors = requests.post(f"http://{min_peer}/quoruminfo").json()["neighbors"]
        min_intersection_neighbors_a = min_intersection_neighbors[id_a]
        min_intersection_neighbors_a.append({API_IP: min_peer_ip, PORT: min_peer_port, QUORUM_ID: id_b})
        min_intersection_neighbors_b = min_intersection_neighbors[id_b]
        min_intersection_neighbors_b.append({API_IP: min_peer_ip, PORT: min_peer_port, QUORUM_ID: id_a})

        min_intersection_ips_a = list(set(requests.get(f"http://{min_peer}/ips/{id_a}").json()))
        min_peer_ip_a = requests.get(f'http://{min_peer}/ip/{id_a}').text
        print(f"current ips a: {min_intersection_ips_a}")
        print(f"self ip a: {min_peer_ip_a}")
        min_intersection_ips_a.append(f"{min_peer_ip_a}:8800")
        min_intersection_ips_b = list(set(requests.get(f"http://{min_peer}/ips/{id_b}").json()))
        min_peer_ip_b = requests.get(f'http://{min_peer}/ip/{id_b}').text
        print(f"current ips b: {min_intersection_ips_b}")
        print(f"self ip b: {min_peer_ip_b}")
        min_intersection_ips_b.append(f"{min_peer_ip_b}:8800")

        print(f"HERE IS SOME IMPORTANT INFO FROM {self.port}")
        print(min_intersection_neighbors_a)
        print(min_intersection_neighbors_b)
        print(min_intersection_ips_a)
        print(min_intersection_ips_b)
        print(len(min_intersection_neighbors_a))
        print(len(min_intersection_neighbors_b))
        print(len(min_intersection_ips_a))
        print(len(min_intersection_ips_b))

        join_a_json = [{**neighbors, DOCKER_IP: ip} for neighbors, ip in zip(min_intersection_neighbors_a, min_intersection_ips_a)]
        join_b_json = [{**neighbors, DOCKER_IP: ip} for neighbors, ip in zip(min_intersection_neighbors_b, min_intersection_ips_b)]

        logging.info("Join A JSON:")
        logging.info(join_a_json)
        logging.info("Join B JSON:")
        logging.info(join_b_json)

        requests.get(f"http://localhost:{self.port}/start/{id_a}/{id_b}")
        requests.post(f"http://localhost:{self.port}/join/{id_a}", json={NEIGHBOURS: join_a_json})
        requests.post(f"http://localhost:{self.port}/join/{id_b}", json={NEIGHBOURS: join_b_json})

        for peer in min_intersection_neighbors_a:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json={"host": f"localhost:{self.port}", "host_quorum": min_intersection[1], "quorum": min_intersection[0]})
        
        for peer in min_intersection_neighbors_b:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json={"host": f"localhost:{self.port}", "host_quorum": min_intersection[0], "quorum": min_intersection[1]})

        time.sleep(30)

        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": id_a,
            "val_key": a.val_key()
        })

        time.sleep(30)

        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": id_b,
            "val_key": b.val_key()
        })

        time.sleep(30)
    
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