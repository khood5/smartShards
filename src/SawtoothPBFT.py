from json import JSONDecodeError

import docker
import json
import time
import logging
import logging.handlers
import os
from pathlib import Path

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
sawtooth_logger = logging.getLogger(__name__)

# name of the docker image to run
DOCKER_IMAGE = "sawtooth:final"
DEFAULT_DOCKER_NETWORK = 'bridge'
IDEAL_VIEW_CHANGE_MILSEC = 30000  # 30 sec
COMMIT_VIEW_CHANGE_MILSEC = 15000  # 15 sec
# key locations in container
USER_KEY = {"priv": "/root/.sawtooth/keys/root.priv", "pub": "/root/.sawtooth/keys/root.pub"}
VALIDATOR_KEY = {"priv": "/etc/sawtooth/keys/validator.priv", "pub": "/etc/sawtooth/keys/validator.pub"}
ADMIN_KEY = {"admin": "/admin.priv"}
# these commands are used to create the genesis block for a PBFT committee, they are listed in the order they should be
# run, they only need to be executed once on one peer
# the sawset genesis command need to have the user keys added to the end in the format '["user_key", "user_key"]'
# some commands (consensus and sawtooth config) need to have the list of peers (by there validator keys) appended to
# the end in the format '["val_key", "val_key", "val_key"]' including the peer that is creating the genesis block
SAWTOOTH_GENESIS_COMMANDS = {"genesis": "sawset genesis --key {user_priv} -o config-genesis.batch -A \'{keys}\'",
                             "consensus_config": "sawset proposal create --key {user_priv} \
                                                                      -o config-consensus.batch \
                                                                      sawtooth.consensus.algorithm.name=pbft \
                                                                      sawtooth.consensus.algorithm.version=1.0 \
                                                                      sawtooth.validator.max_transactions_per_block=1 \
                                                                      sawtooth.validator.block_validation_rules=NofX:1,intkey \
                                                                      sawtooth.publisher.max_batches_per_block=1 \
                                                                      sawtooth.consensus.pbft.members=\'{keys}\' ",
                             "sawtooth_config_command": "sawset proposal create --key {user_priv} \
                                                                      -o pbft-settings.batch \
                                                                      sawtooth.consensus.algorithm.name=pbft \
                                                                      sawtooth.consensus.algorithm.version=1.0 \
                                                                      sawtooth.consensus.pbft.idle_timeout={ideal} \
                                                                      sawtooth.consensus.pbft.commit_timeout={commit} \
                                                                      sawtooth.validator.max_transactions_per_block=1 \
                                                                      sawtooth.validator.block_validation_rules=NofX:1,intkey \
                                                                      sawtooth.publisher.max_batches_per_block=1 \
                                                                      sawtooth.consensus.pbft.members=\'{keys}\' ",
                             "make_genesis": "sawadm genesis \
                                              config-genesis.batch \
                                              config-consensus.batch \
                                              pbft-settings.batch"}

# this command is used to add/remove peers from a committee
# it must be executed on one current member of the committee
# keys are added in the format '["val_key", "val_key", "val_key"]'
SAWTOOTH_UPDATE_PEER_COMMAND = "sawset proposal create \
                             --key {user_priv} sawtooth.consensus.pbft.members=\'{keys}\'"

# Lists all peer IPs in a consensus committee
SAWTOOTH_GET_IPS_COMMAND = "sawtooth peer list -F json"

# Lists all peer IP in a consensus committee
SAWTOOTH_GET_PEERS_COMMAND = "sawtooth settings list --filter sawtooth.consensus.pbft.members --format json"

# this command is used to give peers permission to add/remove other peers from the committee
# it must be executed on one current member of the committee that has permission
# keys are added in the format 'user_key, user_key, user_key' NOTE: this is not the same as when they are listed for the
# genesis command
SAWTOOTH_UPDATE_PERMISSION = "sawset proposal create --key {user_priv} \
                                    sawtooth.settings.vote.authorized_keys=\'{keys}\'"

# the amount of time (sec) to wait for peers to update membership after adding/removing a peer
UPDATE_TIMEOUT = 45

# amount of time (sec) to wait for blockchain catch up
BLOCKCHAIN_CATCHUP = 15

# these commands start PBFT they need to run on every peer in a committee, they are listed in the order they should be
# run
# some of the commands (validator) need to have the list of other peers in the committee appended to in the form
# --peers tcp://172.17.0.3:8800,tcp://172.17.0.4:8800, ...
# this dose not include the peer that the commands are being executed on
# all commands should end with a &
SAWTOOTH_START_COMMANDS = {"validator": 'sawtooth-validator  \
                            --bind component:tcp://127.0.0.1:4004 \
                            --bind network:tcp://{ip}:8800 \
                            --bind consensus:tcp://{ip}:5050 \
                            --endpoint tcp://{ip}:8800 \
                            --maximum-peer-connectivity 10000 \
                            --peers {peers}',
                           "api": 'sawtooth-rest-api -v',
                           "settings_processor": 'settings-tp -v',
                           "client": 'intkey-tp-python -v',
                           "pbft": 'pbft-engine -vv --connect tcp://{ip}:5050'}

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def sawtooth_container_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    sawtooth_logger.propagate = console_logging
    sawtooth_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    sawtooth_logger.addHandler(handler)


def append_keys(keys, command, admin_key=ADMIN_KEY["admin"]):
    keys = '{}'.format(str(keys).replace('\'', '\"'))  # converts list to string in form '["keyVal","keyVal" ...]'
    return command.format(keys=keys, user_priv=admin_key, ideal=IDEAL_VIEW_CHANGE_MILSEC,
                          commit=COMMIT_VIEW_CHANGE_MILSEC)


class SawtoothContainer:
    __client = docker.from_env()
    __admin_key = None

    # starts a sawtooth container and generates root and validator keys
    # does not start PBFT
    def __init__(self, network=DEFAULT_DOCKER_NETWORK):
        self.__container_network = network
        self.__container = self.__client.containers.run(DOCKER_IMAGE, detach=True, network=self.__container_network)
        self.__ip_addr = self.run_command('hostname -i')
        self.run_command('sawtooth keygen')
        self.run_command('sawadm keygen')
        self.__val_key = self.run_command('cat {val_pub}'.format(val_pub=VALIDATOR_KEY["pub"]))
        self.__user_key = self.run_command('cat {user_pub}'.format(user_pub=USER_KEY["pub"]))

    def __del__(self):
        self.__container.stop(timeout=0)
        self.__client.close()
        sawtooth_logger.info('{ip}: shutdown'.format(ip=self.ip()))

    # makes a new genesis block, runs on one and only one peer in a committee
    def make_genesis(self, validator_keys: list, user_keys: list):
        self.set_admin_key(self.run_command('cat {user_pub}'.format(user_pub=USER_KEY["priv"])))
        genesis_command = append_keys(user_keys, SAWTOOTH_GENESIS_COMMANDS["genesis"])
        self.run_command(genesis_command)

        config_command = append_keys(validator_keys, SAWTOOTH_GENESIS_COMMANDS["consensus_config"])
        self.run_command(config_command)

        config_command = append_keys(validator_keys, SAWTOOTH_GENESIS_COMMANDS['sawtooth_config_command'])
        self.run_command(config_command)

        self.run_command(SAWTOOTH_GENESIS_COMMANDS["make_genesis"])

    # starts each of the sawtooth components
    # see https://sawtooth.hyperledger.org/docs/core/nightly/1-2/app_developers_guide/ubuntu_test_network.html ~ step 5
    def start_sawtooth(self, neighbours_ips: list):
        ips = []
        for ip in neighbours_ips:
            if ip != self.__ip_addr:
                ips.append(ip)
        for i in range(len(ips)):
            ips[i] = "tcp://{}:8800".format(ips[i])
        self.set_admin_key()
        self.run_service(SAWTOOTH_START_COMMANDS["validator"].format(ip=self.ip(), peers=', '.join(ips)))
        self.run_service(SAWTOOTH_START_COMMANDS["api"])
        self.run_service(SAWTOOTH_START_COMMANDS["settings_processor"])
        self.run_service(SAWTOOTH_START_COMMANDS["client"])
        self.run_service(SAWTOOTH_START_COMMANDS["pbft"].format(ip=self.ip()))

    # joins a PBFT committee that already exists
    def join_sawtooth(self, ips: list):
        assert (len(ips) >= 4)  # any less and joining is not possible
        self.start_sawtooth(ips)

    # this re-config the committee so that all peers in keys can vote
    def update_committee(self, validator_keys: list, stop_on_failure=False):
        if len(validator_keys) < 4:
            sawtooth_logger.error("!!!!!!------ PEER UPDATING MEMBERSHIP TO BELOW FOUR MEMBERS ------!!!!!!")
            if stop_on_failure:
                return False
        if len(validator_keys) != len(validator_keys):
            sawtooth_logger.error("!!!!!!------ PEER UPDATING MEMBERSHIP VALIDATOR/USER KEY MISMATCH ------!!!!!!")
            sawtooth_logger.error("!!!!!!------        PEER UPDATING MEMBERSHIP UPDATE SKIPPED       ------!!!!!!")
            return False
        if self.__admin_key is None:
            logging.error("{ip}: can not issue update missing admin key".format(ip=self.ip()))
            return False

        logging.info("{ip}: submitted membership update".format(ip=self.ip()))
        update_membership = append_keys(validator_keys, SAWTOOTH_UPDATE_PEER_COMMAND)
        if self.__update_on_chain_settings(update_membership):
            logging.info("{}: update complete".format(self.ip()))
            return True
        else:
            logging.error("{}: UPDATE FAILED".format(self.ip()))
        return False

    def get_ips(self):
        result = (json.dumps(json.loads(self.run_command(SAWTOOTH_GET_IPS_COMMAND))).replace('\\', "")).replace(
            "tcp://", "")
        list_start = result.find("[")
        ips_str = (result[list_start:])

        ips = json.loads(ips_str)
        return ips

    # Gets a table of all other peers
    def get_peers(self):
        result = json.dumps(json.loads(self.run_command(SAWTOOTH_GET_PEERS_COMMAND))["settings"][
                                "sawtooth.consensus.pbft.members"]).replace('\\', "")
        list_start = result.find("[")
        peers_str = (result[list_start:])[:-1]

        peers = json.loads(peers_str)
        return peers

    # Notifies other peers of intention to leave
    def leave_network(self, val_key):
        peers = self.get_peers()
        initial_size = len(peers)
        new_network = []

        for key in peers:
            if key != val_key:
                new_network.append(key)

        final_size = len(new_network)

        assert (initial_size - final_size <= 1)

        return self.update_committee(new_network, stop_on_failure=True)

    def rejoin_network(self):
        ips = self.get_ips()
        self.join_sawtooth(ips)

    def __update_on_chain_settings(self, command: str):
        current_chain_size = len(self.blocks()['data'])
        logging.info("{ip}: waiting for chain to increase from {b}".format(ip=self.ip(), b=current_chain_size))
        self.run_command(command)
        # wait for update
        start = time.time()
        retry_attempted = False
        while len(self.blocks()['data']) <= current_chain_size:
            logging.info("{ip}: current length {b}".format(ip=self.ip(), b=len(self.blocks()['data'])))
            end = time.time()
            if end - start > UPDATE_TIMEOUT * 0.75 and retry_attempted is False:
                sawtooth_logger.critical("------ UPDATE RETRY ------")
                self.run_command(command)
                retry_attempted = True
                time.sleep(1)
            if end - start > UPDATE_TIMEOUT:
                sawtooth_logger.critical("------ UPDATE TIMEOUT ------")
                return False
            time.sleep(1)
        return True

    def submit_tx(self, key: str, val: str):
        self.run_command('intkey set {key} {val}'.format(key=key, val=val))

    def get_tx(self, key):
        value = self.run_command('intkey show {key}'.format(key=key))
        value = value.split(':')[1].strip()
        return value

    def val_key(self):
        return self.__val_key

    def user_key(self):
        return self.__user_key

    def admin_key(self):
        return self.__admin_key

    def container_id(self):
        return self.__container.id

    def set_admin_key(self, key=None):
        if SawtoothContainer.__admin_key is None:
            SawtoothContainer.__admin_key = key
        self.run_command('/bin/sh -c "echo {key} > {file}"'.format(key=SawtoothContainer.__admin_key,
                                                                   file=ADMIN_KEY['admin']))

    def id(self):
        if self.__container is None:
            return None
        return self.__container.id

    # returns the network the container was connected to
    def attached_network(self):
        return self.__container_network

    # all peers communicate via a virtual network hosted by docker. Docker runs DHCP and will assign each peer a new IP
    # peers can access other peers by there ip address and only there ip address, there is no DNS
    def ip(self):
        try:
            return self.__ip_addr
        except AttributeError:
            return "no ip for {}".format(self.__container)

    # return the blocks in this peers blockchain
    def blocks(self):
        blocks = self.sawtooth_api('http://localhost:8008/blocks')
        if 'data' in blocks:
            return blocks
        else:
            logging.warning("{ip}: could not get blocks got {b} instead".format(ip=self.ip(), b=blocks))
            return json.loads(json.dumps({'data': []}))

    # returns all currently running process in this peer
    def top(self):
        return self.__container.top()

    # run a command in a container, will return the output of the command
    def run_command(self, command: str):
        sawtooth_logger.info("{ip}:running command:  {command}".format(ip=self.ip(), command=command))
        result = self.__container.exec_run(command).output.decode('utf-8').strip()
        sawtooth_logger.info("{ip}:command result:  {result}".format(ip=self.ip(), result=result))
        return result

    # start a service inside the container, will not return any output
    def run_service(self, service_start_command: str):
        sawtooth_logger.info("{ip}:starting service:  {request}".format(ip=self.ip(), request=service_start_command))
        self.__container.exec_run(service_start_command, detach=True)

    # gets some json from the peer via a URL (ex: http://localhost:8008/blocks)
    def sawtooth_api(self, request: str):
        sawtooth_logger.info("{ip}:api request:  {request}".format(ip=self.ip(), request=request))
        command = 'curl -sS {}'.format(request)
        result = self.__container.exec_run(command).output.decode('utf-8').strip()
        sawtooth_logger.debug("{ip}:api result: {result}".format(ip=self.ip(), result=result))
        if result != "curl: (7) Failed to connect to localhost port 8008: Connection timed out" and \
                result != "curl: (56) Recv failure: Connection timed out" and \
                result != "curl: (7) Failed to connect to localhost port 8008: Connection refused":
            return json.loads(result)
        else:
            sawtooth_logger.warning("{ip}: api failed to complete request {t}:{r}".format(ip=self.ip(),
                                                                                          t=type(result),
                                                                                          r=result))
            return json.loads(json.dumps({'data': []}))