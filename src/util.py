import docker as docker_api
from src.api.constants import API_IP, QUORUMS, PORT, QUORUM_ID, PBFT_INSTANCES, NEIGHBOURS
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.SmartShardPeer import SmartShardPeer
import os
import logging
import logging.handlers
import requests
import socket
import json

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
util_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB
URL_REQUEST = "http://{hostname}:{port}/"


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


# makes a test committee of user defined size
def make_sawtooth_committee(size: int):
    peers = [SawtoothContainer() for _ in range(size)]
    peers[0].make_genesis([p.val_key() for p in peers], [p.user_key() for p in peers])
    committee_ips = [p.ip() for p in peers]
    for p in peers:
        p.join_sawtooth(committee_ips)

    done = False
    while not done:
        done = True
        for p in peers:
            if len(p.blocks()['data']) != 1:
                done = False

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
    for neighbor_peer_port in network:
        neighbor_membership = [network[neighbor_peer_port].api.config[PBFT_INSTANCES].committee_id_a,
                               network[neighbor_peer_port].api.config[PBFT_INSTANCES].committee_id_b]

        if quorum == neighbor_membership[0]:
            neighbors.append({
                API_IP: "{}".format(socket.gethostbyname(socket.gethostname())),
                PORT: "{}".format(neighbor_peer_port),
                QUORUM_ID: "{}".format(neighbor_membership[1])
            })

        if quorum == neighbor_membership[1]:
            neighbors.append({
                API_IP: "{}".format(socket.gethostbyname(socket.gethostname())),
                PORT: "{}".format(neighbor_peer_port),
                QUORUM_ID: "{}".format(neighbor_membership[0])
            })

    return neighbors


# starts a set of peers on the same host (differentiated by port number)
# returns a dict {portNumber : SmartShardPeer}
def make_intersecting_committees_on_host(number_of_committees: int, intersections: int):
    port_number = 5000
    inter = make_intersecting_committees(number_of_committees, intersections)
    peers = {}
    for i in inter:
        peers[port_number] = (SmartShardPeer(i, port_number))
        port_number += 1
        peers[-1].start()

    for port in peers:
        quorum_id = peers[port].api.config[PBFT_INSTANCES].committee_id_a
        other_peers = [p for p in peers if peers[p].port != port]
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        peers_ip = socket.gethostbyname(socket.gethostname())
        url = "http://{ip}:{port}/add/{quorum}".format(ip=peers_ip, port=port, quorum=quorum_id)
        requests.post(url, json=add_json)

        quorum_id = peers[port].api.config[PBFT_INSTANCES].committee_id_b
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        url = "http://{ip}:{port}/add/{quorum}".format(ip=peers_ip, port=port, quorum=quorum_id)
        requests.post(url, json=add_json)

    return peers
