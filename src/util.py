import docker as docker_api
from src.api.constants import API_IP, PORT, QUORUM_ID, PBFT_INSTANCES, NEIGHBOURS, QUORUMS, DOCKER_IP
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import DEFAULT_DOCKER_NETWORK
from src.Intersection import Intersection
from src.SmartShardPeer import SmartShardPeer
import os
import logging
import logging.handlers
import requests
import socket
import json
import time
from contextlib import closing

UPDATE_CONFIRMATION = 60

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
util_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def util_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    util_logger.propagate = console_logging
    util_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    util_logger.addHandler(handler)


def stop_all_containers():
    client = docker_api.from_env()
    for c in client.containers.list():
        c.stop(timeout=0)
    client.close()


# gets a list of all running container ids
def get_container_ids():
    client = docker_api.from_env()
    ids = []
    for c in client.containers.list():
        ids.append(c.id)
    client.close()
    return ids


def check_for_confirmation(peers, number_of_tx, tx_key="NO_KEY_GIVEN", timeout=UPDATE_CONFIRMATION):
    done = False
    start = time.time()
    while not done:
        time.sleep(0.5)
        done = True

        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            if number_of_tx > peers_blockchain:
                done = False
                break
        if time.time() - start > timeout:
            for p in peers:
                peers_blockchain = len(p.blocks()['data'])
                result = p.get_tx(tx_key)
                logging.critical("{ip}: TIMEOUT unable to confirm tx {key}:{r}".format(ip=p.ip(), key=tx_key,
                                                                                       r=result))
                logging.critical("{ip}: TIMEOUT blockchain length:{l} waiting for {nt}".format(ip=p.ip(),
                                                                                               l=peers_blockchain,
                                                                                               nt=number_of_tx))
            return False
    return True


# makes a test committee of user defined size
def make_sawtooth_committee(size: int, network=DEFAULT_DOCKER_NETWORK):
    if size < 4:
        logging.error("COMMITTEE IMPOSSIBLE: can not make committees of less then 4 members, {} asked for".format(size))
        return []
    if size < 7:
        logging.warning("COMMITTEE UNSTABLE: making committees of less then 7 members can lead to issues with adding "
                        "and removing. ")

    peers = [SawtoothContainer(network) for _ in range(size)]
    peers[0].make_genesis([p.val_key() for p in peers], [p.user_key() for p in peers])

    committee_ips = [p.ip() for p in peers]
    for p in peers:
        p.join_sawtooth(committee_ips)

    # if the there are a lot of containers running wait longer for process to start
    time.sleep(5 * size)

    done = False
    while not done:
        done = True
        for p in peers:
            if len(p.blocks()['data']) < 1:
                logging.info("Peer {ip} could not get genesis block\n"
                             "     blocks:{b}".format(ip=p.ip(), b=p.blocks()['data']))
                done = False
                time.sleep(0.5)
                break

    return peers


def make_single_intersection(instances: list, committee_size: int):
    peers = []
    for row in range(committee_size + 1):
        for column in range(row, committee_size):
            peers.append(Intersection(instances[row][column], instances[column + 1][row], row, column + 1), )
            util_logger.info("In committee {a} committee Member {a_ip} matches {b_ip} in committee {b}".format(
                a=row,
                a_ip=instances[row][column].ip(),
                b_ip=instances[column + 1][row].ip(),
                b=column + 1))

    return peers


def make_intersecting_committees(number_of_committees: int, intersections: int):
    pbft_instance = []
    committee_size = (number_of_committees - 1) * intersections
    for _ in range(number_of_committees):
        pbft_instance.append(make_sawtooth_committee(committee_size))

    peers = []
    # for committees with more then one intersection they are made by combining a series
    # of single intersecting committees, each entry in the series is a section
    for intersection in range(intersections):
        section_size = int(committee_size / intersections)
        start_of_section = section_size * intersection
        end_of_section = start_of_section + section_size + 1  # one past last element
        committee_section = [c[start_of_section:end_of_section] for c in pbft_instance]
        intersecting_peers = make_single_intersection(committee_section, section_size)
        peers += intersecting_peers
    return peers


def get_neighbors(quorum, network: map):
    neighbors = []
    for neighbor_port, neighbor_peer in network.items():
        id_a = neighbor_peer.app.api.config[PBFT_INSTANCES].committee_id_a
        id_b = neighbor_peer.app.api.config[PBFT_INSTANCES].committee_id_b

        if quorum == id_a:
            neighbors.append({
                API_IP: "localhost",
                DOCKER_IP: neighbor_peer.app.api.config[PBFT_INSTANCES].ip(id_a),
                PORT: f"{neighbor_port}",
                QUORUM_ID: f"{id_b}"
            })

        if quorum == id_b:
            neighbors.append({
                API_IP: "localhost",
                DOCKER_IP: neighbor_peer.app.api.config[PBFT_INSTANCES].ip(id_b),
                PORT: f"{neighbor_port}",
                QUORUM_ID: f"{id_a}"
            })

    return neighbors


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


# starts a set of peers on the same host (differentiated by port number)
# returns a dict {portNumber : SmartShardPeer}
def make_intersecting_committees_on_host(number_of_committees: int, intersections: int):
    inter = make_intersecting_committees(number_of_committees, intersections)
    peers = {}
    for i in inter:
        port_number = find_free_port()
        peers[port_number] = SmartShardPeer(port_number)
        peers[port_number].start(i)

    for port, peer in peers.items():
        other_peers = {other_port: other_peer for other_port, other_peer in peers.items() if other_port != port}

        quorum_id = peer.app.api.config[PBFT_INSTANCES].committee_id_a
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        url = "http://localhost:{port}/add/{quorum}".format(port=port, quorum=quorum_id)
        requests.post(url, json=add_json, headers={"Connection":"close"})

        quorum_id = peers[port].app.api.config[PBFT_INSTANCES].committee_id_b
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        url = "http://localhost:{port}/add/{quorum}".format(port=port, quorum=quorum_id)
        requests.post(url, json=add_json, headers={"Connection":"close"})

    return peers
