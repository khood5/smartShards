import docker
import json

# these commands are used to create the genesis block for a PBFT committee, they are listed in the order they should be run
# they only need to be executed once on one peer
# some commands (consensus and pbft config) need to have the list of peers (by there keys) appended to the end between
# '' including the peer that is creating the genesis block
SAWTOOTH_GENESIS_COMMANDS = {"genesis": "sawset genesis --key /root/.sawtooth/keys/root.priv -o config-genesis.batch",
                             "consensus_config": "sawset proposal create --key /root/.sawtooth/keys/root.priv -o config-consensus.batch \
                                                                              sawtooth.consensus.algorithm.name=pbft \
                                                                              sawtooth.consensus.algorithm.version=1.0 \
                                                                              sawtooth.consensus.pbft.members=",
                             "pbft_config": "sawset proposal create --key /root/.sawtooth/keys/root.priv -o pbft-settings.batch \
                                                                              sawtooth.consensus.algorithm.name=pbft \
                                                                              sawtooth.consensus.algorithm.version=1.0 \
                                                                              sawtooth.consensus.pbft.members=",
                             "make_genesis": "sawadm genesis config-genesis.batch config-consensus.batch pbft-settings.batch"}

# these commands start PBFT they need to run on every peer in a committee, they are listed in the order they should be run
# some of the commands (validator) need to have the list of other peers in the committee appended to in the form
# --peers tcp://172.17.0.3:8800,tcp://172.17.0.4:8800, ...
# this dose not include the peer that the commands are being executed on
# all commands should end with a &
SAWTOOTH_START_COMMANDS = {"validator": 'sawtooth-validator \
                            --bind component:tcp://127.0.0.1:4004 \
                            --bind network:tcp://__IP__:8800 \
                            --bind consensus:tcp://__IP__:5050 \
                            --endpoint tcp://__IP__:8800 \
                            --peers ',
                           "api": 'sawtooth-rest-api -v',
                           "transaction_processor": 'settings-tp -v',
                           "client": 'intkey-tp-python -v',
                           "pbft": 'pbft-engine -vv --connect tcp://__IP__:5050'}


# takes a list of containers and a command appends the validator.pub keys to the end of the command
# keys are added in the form ['key', 'key' ...]
def append_keys(containers, command):
    keys = []
    for c in containers:
        keys.append(c.key())
    keys = str(keys).replace('\'', '\"')  # converts list to string in form ["keyVal","keyVal" ...]
    return command + '\'{}\''.format(keys)


class SawtoothContainer:

    def __init__(self):
        self.__client = docker.from_env()
        self.__container = None
        self.__ip_addr = None
        self.__key = None

    def __del__(self):
        self.__client.close()

    # starts a sawtooth container (peer) without starting PBFT
    # this is needed because each peer must generate there keys before PBFT starts
    # in addition when adding a new peer it has to catch up to the others first
    # i.e. sync it's blockchain to the others before starting PBFT
    def start_instance(self):
        self.__container = self.__client.containers.run('sawtooth:final', detach=True)
        self.run_command('sawtooth keygen')
        self.run_command('sawadm keygen')
        self.__ip_addr = self.run_command('hostname -i')
        self.__key = self.run_command('cat /etc/sawtooth/keys/validator.pub')

    # makes a new genesis block, runs on one and only one peer in a committee
    def make_genesis(self, neighbours: list):
        self.run_command(SAWTOOTH_GENESIS_COMMANDS["genesis"])

        config_command = append_keys(neighbours, SAWTOOTH_GENESIS_COMMANDS["consensus_config"])
        self.run_command(config_command)

        config_command = append_keys(neighbours, SAWTOOTH_GENESIS_COMMANDS["pbft_config"])
        self.run_command(config_command)

        self.run_command(SAWTOOTH_GENESIS_COMMANDS["make_genesis"])

    # starts PBFT
    def start_sawtooth(self, neighbours: list):
        start_validator = self.__append_endpoints(neighbours, SAWTOOTH_START_COMMANDS["validator"])
        start_validator = start_validator.replace('__IP__', self.ip())
        self.run_service(start_validator)

        self.run_service(SAWTOOTH_START_COMMANDS["api"])
        self.run_service(SAWTOOTH_START_COMMANDS["transaction_processor"])
        self.run_service(SAWTOOTH_START_COMMANDS["client"])
        self.run_service(SAWTOOTH_START_COMMANDS["pbft"].replace('__IP__', self.ip()))

    # crashes  a peer
    def stop_instance(self):
        self.__container.stop(timeout=0)

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
        return self.__container.exec_run(command).output.decode('utf-8').strip()

    # start a service inside the container, will not return any output
    def run_service(self, service_start_command: str):
        self.__container.exec_run(service_start_command, detach=True)

    # gets some json from the peer via a URL (ex: http://localhost:8008/blocks)
    def sawtooth_api(self, request: str):
        command = 'curl -sS {}'.format(request)
        result = self.run_command(command)
        return json.loads(result)

    # takes a list of containers and a command appends the endpoints of each sawtooth instance to the command
    # endpoints are added in the form [tcp://172.17.0.2:8800,tcp://172.17.0.3:8800, ...]
    # will skip this peer
    def __append_endpoints(self, containers, command):
        ips = []
        for c in containers:
            if c.ip != self.__ip_addr:
                ips.append(c.ip())
        for i in range(len(ips)):
            ips[i] = "tcp://{}:8800".format(ips[i])

        return command + ', '.join(ips)
