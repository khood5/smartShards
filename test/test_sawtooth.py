import unittest
import time
import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer


def stop_all_containers():
    docker = dockerapi.from_env()
    for c in docker.containers.list():
        c.stop()
    docker.close()


# gets a list of all running container ids
def get_container_ids():
    docker = dockerapi.from_env()
    ids = []
    for c in docker.containers.list():
        ids.append(c.id)
    docker.close()
    return ids


class TestSawtoothMethods(unittest.TestCase):

    def test_start_container(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))

        # test that container is made empty
        sawtooth_instance = SawtoothContainer()
        self.assertIs(sawtooth_instance.id(), None)
        self.assertIs(sawtooth_instance.ip(), None)
        self.assertIs(sawtooth_instance.key(), None)

        # test that once an instance is started that it has an id, ip and key
        sawtooth_instance.start_instance()
        self.assertEqual(len(docker.containers.list()), 1)
        self.assertIsNot(sawtooth_instance.id(), None)
        self.assertIsNot(sawtooth_instance.ip(), None)
        self.assertIsNot(sawtooth_instance.key(), None)

        container_ip = docker.containers.list()[0].exec_run("hostname -i").output.decode('utf-8').strip()
        container_key = docker.containers.list()[0].exec_run("cat /etc/sawtooth/keys/validator.pub").output.decode('utf-8').strip()
        self.assertEqual(sawtooth_instance.id(), docker.containers.list()[0].id)
        self.assertEqual(sawtooth_instance.ip(), container_ip)
        self.assertEqual(sawtooth_instance.key(), container_key)
        number_of_running_processes = len(docker.containers.list()[0].top()['Processes'][0])
        # should only be 2 processes bash and tail -f /dev/null
        # each process has 4 columns so 2*4 = 8
        self.assertEqual(number_of_running_processes, 8)

        # test that containers are made unique
        sawtooth_instance_2nd = SawtoothContainer()

        # test that container is made empty
        self.assertIs(sawtooth_instance_2nd.id(), None)
        self.assertIs(sawtooth_instance_2nd.ip(), None)
        self.assertIs(sawtooth_instance_2nd.key(), None)

        sawtooth_instance_2nd.start_instance()
        self.assertEqual(len(docker.containers.list()), 2)
        # tests that the two instance to not have the same IP or Key
        self.assertNotEqual(sawtooth_instance.id(), sawtooth_instance_2nd.id())
        self.assertNotEqual(sawtooth_instance.ip(), sawtooth_instance_2nd.ip())
        self.assertNotEqual(sawtooth_instance.key(), sawtooth_instance_2nd.key())

        # clean up
        stop_all_containers()
        docker.close()

    def test_kill_container(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))

        sawtooth_instance = SawtoothContainer()
        sawtooth_instance.start_instance()
        self.assertEqual(len(docker.containers.list()), 1)
        self.assertIn(sawtooth_instance.id(), get_container_ids())

        sawtooth_instance_2nd = SawtoothContainer()
        sawtooth_instance_2nd.start_instance()
        self.assertEqual(len(docker.containers.list()), 2)
        self.assertIn(sawtooth_instance.id(), get_container_ids())
        self.assertIn(sawtooth_instance_2nd.id(), get_container_ids())

        # test that if one instance is stop only one instance stops
        sawtooth_instance.stop_instance()
        self.assertEqual(len(docker.containers.list()), 1)
        self.assertIn(sawtooth_instance_2nd.id(), get_container_ids())

        sawtooth_instance_2nd.stop_instance()
        self.assertEqual(len(docker.containers.list()), 0)

        # clean up
        stop_all_containers()
        docker.close()

    def test_committee_init_setup(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))

        # a committee needs a min of 4 members. Any less peers can not join or leave cleanly and they can not confirm
        # new transactions
        peers = [None, None, None, None]
        for i in range(len(peers)):
            peers[i] = SawtoothContainer()
            peers[i].start_instance()

        # make sure all containers have started
        self.assertEqual(len(docker.containers.list()), 4)

        peers[0].make_genesis(peers)
        for p in peers:
            p.start_sawtooth(peers)

        # make sure all peers are running
        for p in peers:
            self.assertIn('sawtooth-validator',p.top()['Processes'][2][-1])
            self.assertIn('/usr/bin/python3 /usr/bin/sawtooth-rest-api -v', p.top()['Processes'][3][-1])
            self.assertIn('settings-tp -v', p.top()['Processes'][4][-1])
            self.assertIn('/usr/bin/python3 /usr/bin/intkey-tp-python -v', p.top()['Processes'][5][-1])
            self.assertIn('pbft-engine -vv --connect', p.top()['Processes'][6][-1])

        # makes sure genesis block is in each peer
        for p in peers:
            blocks = p.sawtooth_api('http://localhost:8008/blocks')['data']
            self.assertEqual(len(blocks), 1)

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_config =  p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # test transaction confirmation
        number_of_tx = 1
        for p in peers:
            p.run_command('intkey set test{} 999'.format(number_of_tx))
            number_of_tx += 1
            time.sleep(2)  # make sure TX has time to be confirmed
            blockchain_size = len(p.sawtooth_api('http://localhost:8008/blocks')['data'])
            self.assertEqual(blockchain_size, number_of_tx)

        # test that committee breaks if members drop below 4
        peers[0].stop_instance()
        peers.pop(0)

        blockchain_size = len(peers[1].sawtooth_api('http://localhost:8008/blocks')['data'])
        for p in peers:
            p.run_command('intkey set fail 000')
            time.sleep(2)
            peers_blockchain = len(p.sawtooth_api('http://localhost:8008/blocks')['data'])
            self.assertEqual(peers_blockchain, blockchain_size)

        stop_all_containers()
        docker.close()

    def test_peer_join(self):
        print("test_join")

    def test_peer_leave(self):
        print("leave test")


if __name__ == '__main__':
    print("RUNNING {} TESTS".format(SawtoothContainer().__class__.__name__))
    unittest.main()
