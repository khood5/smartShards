import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer
from src.Peer import Peer
import os
import logging
import logging.handlers

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
    client = dockerapi.from_env()
    for c in client.containers.list():
        c.stop(timeout=0)
    client.close()


# gets a list of all running container ids
def get_container_ids():
    client = dockerapi.from_env()
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


# makes 2 quorums each with size number of peers (with whole committee intersection i.e. each peer is in both quorums)
def make_peer_committees(size: int, id_a=1, id_b=2):
    containers_a = make_sawtooth_committee(size)
    containers_b = make_sawtooth_committee(size)
    peers = [Peer(containers_a[i], containers_b[i], id_a, id_b) for i in range(size)]

    return peers


def make_intersecting_committees(number_of_committees: int, intersections: int):
    committees = []
    committee_size = (number_of_committees - 1) * intersections
    for _ in range(number_of_committees):
        committees.append(make_sawtooth_committee(committee_size))

    peers = []
    for row in range(len(committees)):
        for column in range(row, committee_size):
            peers.append(Peer(committees[row][column], committees[column + 1][row], row, column + 1), )
            util_logger.info("In committee {a} committee Member {a_ip} matches {b_ip} in committee {b}".format(
                a=row,
                a_ip=committees[row][column].ip(),
                b_ip=committees[column + 1][row].ip(),
                b=column + 1))

    return peers
