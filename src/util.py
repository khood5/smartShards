import docker as docker_api
from src.api.constants import API_IP, QUORUMS, QUORUM_ID, PORT
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
import os
import logging
import logging.handlers
import requests

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


# get plain text from HTTP GET response
def get_plain_test(response):
    return response.data.decode("utf-8")


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


# this function is made to work with a flask app and cannot be used with out passing one to it as app
def forward(app, url_subdirectory: str, quorum_id: str, json_data):
    for this_quorum in app.config[QUORUMS]:
        for intersecting_quorum in app.config[QUORUMS][this_quorum]:
            if intersecting_quorum[QUORUM_ID] == quorum_id:
                url = URL_REQUEST.format(hostname=intersecting_quorum[API_IP],
                                         port=intersecting_quorum[PORT])
                url += url_subdirectory
                app.logger.info("request in quorum this peer is not a member of forwarding to "
                                "{}".format(url))
                forwarding_request = None
                try:
                    forwarding_request = requests.post(url, json=json_data)
                    app.logger.info("response form forward is {}".format(forwarding_request))
                except ConnectionError as e:
                    app.logger.error("{host}:{port} unreachable".format(host=intersecting_quorum[API_IP],
                                                                        port=intersecting_quorum[PORT]))
                    app.logger.error(e)
                return forwarding_request


def make_intersecting_committees_on_host(number_of_committees: int, intersections: int):
    # * 2 because two instance per peer
    pbft_instances = make_intersecting_committees(number_of_committees, intersections)
