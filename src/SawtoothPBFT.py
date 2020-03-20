import docker

# these commands are used to create the genesis block for a PBFT committee, they are listed in the order they should be run
# they only need to be executed once on one peer
# some commands (consensus and pbft config) need to have the list of peers (by there keys) appended to the end between
# '' including the peer that is creating the genesis block
SAWTOOTH_GENESIS_COMMANDS = {"genesis": "sawset genesis --key $HOME/.sawtooth/keys/root.priv -o config-genesis.batch",
                             "consensus_config": "sawset proposal create --key $HOME/.sawtooth/keys/root.priv -o config-consensus.batch \
                                                                              sawtooth.consensus.algorithm.name=pbft \
                                                                              sawtooth.consensus.algorithm.version=1.0 \
                                                                              sawtooth.consensus.pbft.members=",
                             "pbft_config": "sawset proposal create --key $HOME/.sawtooth/keys/root.priv -o pbft-settings.batch \
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
                            --bind network:tcp://$(hostname -i)8800 \
                            --bind consensus:tcp://$(hostname -i):5050 \
                            --endpoint tcp://$(hostname -i):8800 \
                            --peers ',
                           "api": 'sawtooth-rest-api -v &',
                           "transaction_processor": 'settings-tp -v &',
                           "client": 'intkey-tp-python -v &',
                           "pbft": 'pbft-engine -vv --connect tcp://$(hostname -i):5050 &'}


# runs a command in a docker container
def run_command(container: docker.DockerClient.containers, command: str):
    return container.exec_run(command).output.decode('utf-8').strip()


# takes a list of containers and a command appends the validator.pub keys to the end of the command
# keys are added in the form ['key', 'key' ...]
def append_keys(containers, command):
    keys = []
    for c in containers:
        keys.append(c.key())
    keys = str(keys)  # converts list to string in form ['keyVal','keyVal' ...]
    return command + '\'{}\''.format(keys)


# takes a list of containers and a command appends the endpoints of each sawtooth instance to the command
# endpoints are added in the form [tcp://172.17.0.2:8800,tcp://172.17.0.3:8800, ...]
def append_endpoints(containers, command):
    ips = []
    for c in containers:
        ips.append(c.ip)
    for i in range(len(ips)):
        ips[i] = "tcp://{}:8800".format(ips[i])

    return command + ', '.join(ips)


class SawtoothContainer:
    __container: docker.DockerClient.containers = None
    __ip_addr: str = None
    __key: str = None

    def __init__(self):
        self.__container = None
        self.__ip_addr = None
        self.__key = None

    def start_instance(self):
        client = docker.from_env()
        container = client.containers.run('sawtooth:running', detach=True)
        run_command(container, 'sawtooth keygen')
        run_command(container, 'sawadm keygen')
        self.__container = container
        self.__ip_addr = run_command(container, 'hostname -i')
        self.__key = run_command(self.__container, 'cat /etc/sawtooth/keys/validator.pub')

    def make_genesis(self, neighbours: list):
        run_command(self.__container, SAWTOOTH_GENESIS_COMMANDS["genesis"])

        config_command = append_keys(neighbours, SAWTOOTH_GENESIS_COMMANDS["consensus_config"])
        run_command(self.__container, config_command)

        config_command = append_keys(neighbours, SAWTOOTH_GENESIS_COMMANDS["pbft_config"])
        run_command(self.__container, config_command)

        run_command(self.__container, SAWTOOTH_GENESIS_COMMANDS["make_genesis"])

    def start_sawtooth(self, neighbours: list):
        start_validator = append_endpoints(neighbours, SAWTOOTH_START_COMMANDS["validator"]) + '&'
        run_command(self.__container, start_validator)

        run_command(self.__container, SAWTOOTH_START_COMMANDS["api"])
        run_command(self.__container, SAWTOOTH_START_COMMANDS["transaction_processor"])
        run_command(self.__container, SAWTOOTH_START_COMMANDS["client"])
        run_command(self.__container, SAWTOOTH_START_COMMANDS["pbft"])

    def stop_instance(self):
        self.__container.stop()

    def key(self):
        return self.__key

    def id(self):
        if self.__container is None:
            return None
        return self.__container.id

    def ip(self):
        return self.__ip_addr
