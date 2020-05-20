import unittest
import warnings
import time
import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import VALIDATOR_KEY
from src.SawtoothPBFT import USER_KEY
from src.util import stop_all_containers
from src.util import get_container_ids
from src.util import make_sawtooth_committee


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
        self.assertIsNot(sawtooth_instance.val_key(), None)

        container_ip = docker.containers.list()[0].exec_run("hostname -i").output.decode('utf-8').strip()
        container_val_key = docker.containers.list()[0].exec_run("cat {val_pub}".format(val_pub=VALIDATOR_KEY["pub"])) \
            .output.decode('utf-8').strip()
        container_user_key = docker.containers.list()[0].exec_run("cat {user_pub}".format(user_pub=USER_KEY["pub"])) \
            .output.decode('utf-8').strip()

        self.assertEqual(sawtooth_instance.id(), docker.containers.list()[0].id)
        self.assertEqual(sawtooth_instance.ip(), container_ip)
        self.assertEqual(sawtooth_instance.val_key(), container_val_key)
        self.assertEqual(sawtooth_instance.user_key(), container_user_key)
        self.assertNotEqual(sawtooth_instance.user_key(), sawtooth_instance.val_key())

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
        self.assertNotEqual(sawtooth_instance.val_key(), sawtooth_instance_2nd.val_key())
        self.assertNotEqual(sawtooth_instance.user_key(), sawtooth_instance_2nd.user_key())

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

        peers[0].make_genesis([p.val_key() for p in peers], [p.user_key() for p in peers])
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
            blocks = p.blocks()['data']
            self.assertEqual(1, len(blocks))

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        docker.close()

    def test_transaction_confirmation(self):
        peers = make_sawtooth_committee(4)
        number_of_tx = 1
        for p in peers:
            p.submit_tx('test{}'.format(number_of_tx), '999')
            number_of_tx += 1
            time.sleep(3)  # make sure TX has time to be confirmed
            blockchain_size = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, blockchain_size)

    def test_high_transaction_load(self):
        peers = make_sawtooth_committee(5)
        number_of_tx = 1
        i = 0
        for _ in range(99):  # peers start to drop old blocks at 100
            peers[i].submit_tx('test{}'.format(number_of_tx), '999')

            i = i + 1 if i < (len(peers) - 1) else 0  # cycle peers

            number_of_tx += 1
            time.sleep(0.5)  # prevent DOS attack counter measure

        time.sleep(5)  # give the peers some time to catch up
        for p in peers:
            blockchain_size = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, blockchain_size)

    def test_fault_tolerance(self):
        peers = make_sawtooth_committee(7)
        number_of_tx = 1  # genesis

        del peers[0]
        peers[0].submit_tx('test{}'.format(number_of_tx), '999')
        number_of_tx += 1
        time.sleep(80)  # can take some time for peers to commit (potentially 40s for each failed peer)
        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, peers_blockchain)

        # should fail now
        del peers[0]
        peers[0].submit_tx('fail', '000')
        time.sleep(120)
        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, peers_blockchain)

    def test_large_committee(self):
        peers = make_sawtooth_committee(10)

        peers[0].submit_tx('test', '999')
        time.sleep(3)
        for p in peers:
            blocks = p.blocks()['data']
            self.assertEqual(2, len(blocks))

        peers = make_sawtooth_committee(25)
        peers[0].submit_tx('test', '999')
        time.sleep(3)
        for p in peers:
            blocks = p.blocks()['data']
            self.assertEqual(2, len(blocks))

    def test_peer_join(self):
        peers = make_sawtooth_committee(4)
        peers.append(SawtoothContainer())
        peers[-1].join_sawtooth([p.ip() for p in peers])
        peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
        blockchain_size = 3  # genesis+2 tx added 1 for membership and 1 for admin rights of new peer

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        # and make sure they all have the three tx
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_blocks = len(p.blocks()['data'])
            self.assertEqual(blockchain_size, peers_blocks)

            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # check consensus still works
        peers[-1].submit_tx('test', '999')
        blockchain_size += 1
        time.sleep(3)
        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            self.assertEqual(blockchain_size, peers_blockchain)

    def test_committee_growth(self):
        peers = make_sawtooth_committee(4)
        blockchain_size = 1
        for _ in range(21):
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
            blockchain_size += 2

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        # and make sure they all have the three tx
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_blocks = len(p.blocks()['data'])
            self.assertEqual(blockchain_size, peers_blocks)

            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

    # make sure that if all old peers (original ones in the committee) crash the committee can proceed
    def test_new_peer_replace_old(self):
        peers = make_sawtooth_committee(4)
        blockchain_size = 1
        for i in range(20):
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            peers[i % 4].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
            blockchain_size += 2

        for _ in range(4):
            del peers[0]

        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        time.sleep(180)  # time need to confirm transactions 40 sec * 4 crashes + 20 for tx to be approved

        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

    def test_peer_leave(self):
        peers = make_sawtooth_committee(7)
        blockchain_size = 1

        old_peer = peers.pop()
        peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
        blockchain_size += 2

        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

        del old_peer

        # make sure consensus still works
        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        time.sleep(3)
        for p in peers:
            self.assertEqual('999', p.get_tx('test'))
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

        # remove multiple members
        old_peers = peers[:2]
        peers.pop()
        peers.pop()
        peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
        blockchain_size += 2

        del old_peers

        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

        # make sure consensus still works
        peers[0].submit_tx('test2', '888')
        blockchain_size += 1
        time.sleep(3)
        for p in peers:
            self.assertEqual('888', p.get_tx('test2'))
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

    def test_committee_shrink(self):
        peers = make_sawtooth_committee(25)
        blockchain_size = 1
        for _ in range(21):
            old_peer = peers.pop()
            peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
            blockchain_size += 2
            del old_peer

        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        time.sleep(3)
        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))
            self.assertEqual('999', p.get_tx('test'))

    def test_committee_churn(self):
        peers = make_sawtooth_committee(4)
        blockchain_size = 1
        for _ in range(4):
            # add new peer
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
            blockchain_size += 2

            # remove old peer
            old_peer = peers.pop(0)
            peers[0].update_committee([p.val_key() for p in peers], [p.user_key() for p in peers])
            blockchain_size += 2
            del old_peer

        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        time.sleep(3)
        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))
            self.assertEqual('999', p.get_tx('test'))

    def test_concurrent_committees(self):
        set_a = make_sawtooth_committee(4)
        set_b = make_sawtooth_committee(4)
        tx_a = 'test_a'
        tx_b = 'test_b'
        set_a[0].submit_tx(tx_a, '999')
        set_b[0].submit_tx(tx_b, '888')
        time.sleep(3)
        for p in set_a:
            self.assertEqual(2, len(p.blocks()['data']))

        for p in set_b:
            self.assertEqual(2, len(p.blocks()['data']))


if __name__ == '__main__':
    unittest.main()
