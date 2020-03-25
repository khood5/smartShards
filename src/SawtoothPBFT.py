import docker
import json
import time

# these commands are used to create the genesis block for a PBFT committee, they are listed in the order they should be
# run
# they only need to be executed once on one peer
# some commands (consensus and pbft config) need to have the list of peers (by there keys) appended to the end between
# '' including the peer that is creating the genesis block
SAWTOOTH_GENESIS_COMMANDS = {"genesis": "sawset genesis --key /root/.sawtooth/keys/root.priv -o config-genesis.batch",
                             "consensus_config": "sawset proposal create --key /root/.sawtooth/keys/root.priv \
                                                                      -o config-consensus.batch \
                                                                      sawtooth.consensus.algorithm.name=pbft \
                                                                      sawtooth.consensus.algorithm.version=1.0 \
                                                                      sawtooth.consensus.pbft.members={keys} \
                                                                      sawtooth.settings.vote.authorized-keys={keys}",
                             "sawtooth_config_command": "sawset proposal create --key /root/.sawtooth/keys/root.priv \
                                                                      -o pbft-settings.batch \
                                                                      sawtooth.consensus.algorithm.name=pbft \
                                                                      sawtooth.consensus.algorithm.version=1.0 \
                                                                      sawtooth.consensus.pbft.members={keys}",
                             "make_genesis": "sawadm genesis \
                                              config-genesis.batch \
                                              config-consensus.batch \
                                              pbft-settings.batch"}

SAWTOOTH_ADD_PEER_COMMAND = "sawset proposal create \
                             --key /root/.sawtooth/keys/root.priv sawtooth.consensus.pbft.members={keys}"

SAWTOOTH_ADD_PERMISSION = "sawset proposal create --key /root/.sawtooth/keys/root.priv \
                                    sawtooth.settings.vote.authorized_keys={keys}"

# these commands start PBFT they need to run on every peer in a committee, they are listed in the order they should be
# run
# some of the commands (validator) need to have the list of other peers in the committee appended to in the form
# --peers tcp://172.17.0.3:8800,tcp://172.17.0.4:8800, ...
# this dose not include the peer that the commands are being executed on
# all commands should end with a &
SAWTOOTH_START_COMMANDS = {"validator": 'sawtooth-validator \
                            --bind component:tcp://127.0.0.1:4004 \
                            --bind network:tcp://{ip}:8800 \
                            --bind consensus:tcp://{ip}:5050 \
                            --endpoint tcp://{ip}:8800 \
                            --maximum-peer-connectivity 10000 \
                            --peers {peers}',
                           "api": 'sawtooth-rest-api -v',
                           "transaction_processor": 'settings-tp -v',
                           "client": 'intkey-tp-python -v',
                           "pbft": 'pbft-engine -vv --connect tcp://{ip}:5050'}


# takes a list of containers and a command appends the validator.pub keys to the end of the command
# keys are added in the form ['key', 'key' ...]
def append_keys(keys, command):
    keys = str(keys).replace('\'', '\"')  # converts list to string in form ["keyVal","keyVal" ...]
    return command.format(keys='\'{}\''.format(keys))


class SawtoothContainer:

    # dose not start PBFT
    def __init__(self):
        self.__client = docker.from_env()
        self.__container = self.__client.containers.run('sawtooth:final', detach=True)
        self.run_command('sawtooth keygen')
        self.run_command('sawadm keygen')
        self.__ip_addr = self.run_command('hostname -i')
        self.__key = self.run_command('cat /etc/sawtooth/keys/validator.pub')

    def __del__(self):
        self.__container.stop(timeout=0)
        self.__client.close()

    # makes a new genesis block, runs on one and only one peer in a committee
    def make_genesis(self, keys: list):
        self.run_command(SAWTOOTH_GENESIS_COMMANDS["genesis"])

        config_command = append_keys(keys, SAWTOOTH_GENESIS_COMMANDS["consensus_config"])
        print(config_command)
        print(self.run_command('cat /root/.sawtooth/keys/root.priv'))
        self.run_command(config_command)

        config_command = append_keys(keys, SAWTOOTH_GENESIS_COMMANDS['sawtooth_config_command'])
        print(config_command)
        print(self.run_command('cat /root/.sawtooth/keys/root.priv'))
        self.run_command(config_command)

        self.run_command(SAWTOOTH_GENESIS_COMMANDS["make_genesis"])

    # starts PBFT
    def start_sawtooth(self, neighbours_ips: list):
        print(self.ip())
        ips = []
        for ip in neighbours_ips:
            if ip != self.__ip_addr:
                ips.append(ip)
        for i in range(len(ips)):
            ips[i] = "tcp://{}:8800".format(ips[i])

        self.run_service(SAWTOOTH_START_COMMANDS["validator"].format(ip=self.ip(), peers=', '.join(ips)))
        print("    {}".format(SAWTOOTH_START_COMMANDS["validator"].format(ip=self.ip(), peers=', '.join(ips))))

        self.run_service(SAWTOOTH_START_COMMANDS["api"])
        print("    {}".format(SAWTOOTH_START_COMMANDS["api"]))

        self.run_service(SAWTOOTH_START_COMMANDS["transaction_processor"])
        print("    {}".format(SAWTOOTH_START_COMMANDS["transaction_processor"]))

        self.run_service(SAWTOOTH_START_COMMANDS["client"])
        print("    {}".format(SAWTOOTH_START_COMMANDS["client"]))

        self.run_service(SAWTOOTH_START_COMMANDS["pbft"].format(ip=self.ip()))
        print("    {}".format(SAWTOOTH_START_COMMANDS["pbft"].format(ip=self.ip())))

    # joins a PBFT committee that already exists
    def join_sawtooth(self, ips: list):
        assert (len(ips) >= 4)  # any less and joining is not possible
        self.start_sawtooth(ips)
        time.sleep(30)  # wait for peers to accept the new peer

    def add_peer_to_committee(self, keys: list):
        add_permission = SAWTOOTH_ADD_PERMISSION.format(keys='\'{}\''.format(keys))
        add_command = append_keys(keys, SAWTOOTH_ADD_PEER_COMMAND)
        print(add_command)
        self.run_command(add_command)
        print(add_permission)
        a = self.run_command(add_permission)
        print(a)

    # gets this peers unique key used for signing blocks
    def key(self):
        return self.__key

    # gets this peers id
    def id(self):
        if self.__container is None:
            return None
        return self.__container.id

    # gets this peers ip address
    # all peers communicate via a virtual network hosted by docker. Docker runs DHCP and will assign each peer a new IP
    # peers can access other peers by there ip address and only there ip address, there is no DNS
    def ip(self):
        return self.__ip_addr

    # returns all currently running process in this peer
    def top(self):
        return self.__container.top()

    # run a command in a container, will return the output of the command
    def run_command(self, command: str):
        return self.__container.exec_run(command, user='root').output.decode('utf-8').strip()

    # start a service inside the container, will not return any output
    def run_service(self, service_start_command: str):
        self.__container.exec_run(service_start_command, user='root', detach=True)

    # gets some json from the peer via a URL (ex: http://localhost:8008/blocks)
    def sawtooth_api(self, request: str):
        command = 'curl -sS {}'.format(request)
        result = self.run_command(command)
        return json.loads(result)

