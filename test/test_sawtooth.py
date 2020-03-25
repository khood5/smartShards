import unittest
import warnings
import time
import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer


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
def start_test_committee(size: int):
    peers = [SawtoothContainer() for _ in range(size)]
    keys = [p.key() for p in peers]
    peers[0].make_genesis(keys)
    committee_ips = [p.ip() for p in peers]
    for p in peers:
        p.start_sawtooth(committee_ips)

    return peers


class TestSawtoothMethods(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        stop_all_containers()

    def test_start_container(self):
        docker = dockerapi.from_env()

        # test that once an instance is started that it has an id, ip and key
        sawtooth_instance = SawtoothContainer()
        self.assertEqual(1, len(docker.containers.list()))
        self.assertIsNot(sawtooth_instance.id(), None)
        self.assertIsNot(sawtooth_instance.ip(), None)
        self.assertIsNot(sawtooth_instance.key(), None)

        container_ip = docker.containers.list()[0].exec_run("hostname -i").output.decode('utf-8').strip()
        container_key = docker.containers.list()[0].exec_run("cat /etc/sawtooth/keys/validator.pub").output.decode(
            'utf-8').strip()
        self.assertEqual(sawtooth_instance.id(), docker.containers.list()[0].id)
        self.assertEqual(sawtooth_instance.ip(), container_ip)
        self.assertEqual(sawtooth_instance.key(), container_key)
        number_of_running_processes = len(docker.containers.list()[0].top()['Processes'][0])
        # should only be 2 processes bash and tail -f /dev/null
        # each process has 4 columns so 2*4 = 8
        self.assertEqual(8, number_of_running_processes)

        # test that containers are made unique
        sawtooth_instance_2nd = SawtoothContainer()

        self.assertEqual(2, len(docker.containers.list()))
        # tests that the two instance to not have the same IP or Key
        self.assertNotEqual(sawtooth_instance.id(), sawtooth_instance_2nd.id())
        self.assertNotEqual(sawtooth_instance.ip(), sawtooth_instance_2nd.ip())
        self.assertNotEqual(sawtooth_instance.key(), sawtooth_instance_2nd.key())

        # clean up
        docker.close()

    def test_kill_container(self):
        docker = dockerapi.from_env()

        sawtooth_instance = SawtoothContainer()
        self.assertEqual(1, len(docker.containers.list()))
        self.assertIn(sawtooth_instance.id(), get_container_ids())

        sawtooth_instance_2nd = SawtoothContainer()
        self.assertEqual(2, len(docker.containers.list()))
        self.assertIn(sawtooth_instance.id(), get_container_ids())
        self.assertIn(sawtooth_instance_2nd.id(), get_container_ids())

        # test that if one instance is stop only one instance stops
        del sawtooth_instance
        self.assertEqual(1, len(docker.containers.list()))
        self.assertIn(sawtooth_instance_2nd.id(), get_container_ids())

        del sawtooth_instance_2nd
        self.assertEqual(0, len(docker.containers.list()))

        # clean up
        docker.close()

    def test_committee_init_setup(self):
        docker = dockerapi.from_env()

        # a committee needs a min of 4 members. Any less peers can not join or leave cleanly and they can not confirm
        # new transactions
        peers = [None, None, None, None]
        for i in range(len(peers)):
            peers[i] = SawtoothContainer()

        # make sure all containers have started
        self.assertEqual(4, len(docker.containers.list()))

        keys = [p.key() for p in peers]
        peers[0].make_genesis(keys)
        committee_ips = [p.ip() for p in peers]
        for p in peers:
            p.start_sawtooth(committee_ips)

        # make sure all peers are running
        process_names = []
        for p in peers:
            for process in p.top()['Processes']:
                process_names.append(process[-1])
            self.assertIn('sawtooth-validator', [i for i in process_names if 'sawtooth-validator' in i][0])
            self.assertIn('/usr/bin/python3 /usr/bin/sawtooth-rest-api -v', process_names)
            self.assertIn('settings-tp -v', process_names)
            self.assertIn('/usr/bin/python3 /usr/bin/intkey-tp-python -v', process_names)
            self.assertIn('pbft-engine -vv --connect',
                          [i for i in process_names if 'pbft-engine -vv --connect' in i][0])

        # makes sure genesis block is in each peer
        for p in peers:
            blocks = p.sawtooth_api('http://localhost:8008/blocks')['data']
            self.assertEqual(1, len(blocks))

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # test transaction confirmation
        number_of_tx = 1
        for p in peers:
            p.run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(2)  # make sure TX has time to be confirmed
            blockchain_size = len(p.sawtooth_api('http://localhost:8008/blocks')['data'])
            self.assertEqual(number_of_tx, blockchain_size)

        # test that committee breaks if members drop below 4
        del peers[0]

        blockchain_size = len(peers[1].sawtooth_api('http://localhost:8008/blocks')['data'])
        for p in peers:
            p.run_command('intkey set fail 000')
            time.sleep(2)
            peers_blockchain = len(p.sawtooth_api('http://localhost:8008/blocks')['data'])
            self.assertEqual(blockchain_size, peers_blockchain)

        # test larger size committee
        peers = start_test_committee(10)
        # makes sure genesis block is in each peer
        for p in peers:
            blocks = p.sawtooth_api('http://localhost:8008/blocks')['data']
            self.assertEqual(1, len(blocks))

        peers = start_test_committee(25)
        for p in peers:
            blocks = p.sawtooth_api('http://localhost:8008/blocks')['data']
            self.assertEqual(1, len(blocks))

        docker.close()

    def test_peer_join(self):
        # test adding to min size
        peers = start_test_committee(4)

        # add some blocks so that the new peer has to catch up
        number_of_tx = 1
        for _ in range(10):
            peers[0].run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(1)
        blockchain_size = len(peers[0].sawtooth_api('http://localhost:8008/blocks')['data'])
        self.assertEqual(11, blockchain_size)

        peers.append(SawtoothContainer())
        peers[-1].join_sawtooth([p.ip() for p in peers])
        peers[0].add_peer_to_committee([p.key() for p in peers])

        # check to make sure peers config has been updated
        self.assertEqual(5, len(peers))
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # test that consensus still runs
        # Note that new peer is submitting request and
        # an old peer is being check for them
        for _ in range(10):
            peers[-1].run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(3)
        time.sleep(30)
        blockchain_size = len(peers[0].sawtooth_api('http://localhost:8008/blocks')['data'])
        self.assertEqual(23, blockchain_size)

        # remove one of the original peers (consensus should still work)
        del peers[0]
        for _ in range(10):
            peers[-1].run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(3)
        time.sleep(30)
        blockchain_size = len(peers[0].sawtooth_api('http://localhost:8008/blocks')['data'])
        self.assertEqual(33, blockchain_size)

        # cycle all old peers out and then test that committee still works
        for _ in range(10):
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            peers[0].add_peer_to_committee([p.key() for p in peers])
            del peers[0]

        for _ in range(10):
            peers[-1].run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(3)
        time.sleep(30)
        blockchain_size = len(peers[0].sawtooth_api('http://localhost:8008/blocks')['data'])
        self.assertEqual(43, blockchain_size)

    def test_peer_leave(self):
        print("leave test")


if __name__ == '__main__':
    print("RUNNING {} TESTS".format(SawtoothContainer().__class__.__name__))
    unittest.main()
