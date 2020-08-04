import unittest
import warnings
import time
import docker as docker_api
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import VALIDATOR_KEY
from src.SawtoothPBFT import USER_KEY
from src.SawtoothPBFT import DEFAULT_DOCKER_NETWORK
from src.SawtoothPBFT import IDEAL_VIEW_CHANGE_MILSEC
from src.util import stop_all_containers
from src.util import get_container_ids
from src.util import make_sawtooth_committee
from src.util import check_for_confirmation
import gc

VIEW_CHANGE_WAIT_TIME_SEC = IDEAL_VIEW_CHANGE_MILSEC / 1000  # ms to seconds


class TestSawtoothMethods(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = docker_api.from_env()
        if len(docker.containers.list()) != 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        gc.collect()
        stop_all_containers()

    def test_start_container(self):
        docker = docker_api.from_env()

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
        container_network = DEFAULT_DOCKER_NETWORK

        self.assertEqual(sawtooth_instance.id(), docker.containers.list()[0].id)
        self.assertEqual(sawtooth_instance.ip(), container_ip)
        self.assertEqual(sawtooth_instance.val_key(), container_val_key)
        self.assertEqual(sawtooth_instance.user_key(), container_user_key)
        self.assertNotEqual(sawtooth_instance.user_key(), sawtooth_instance.val_key())
        self.assertEqual(sawtooth_instance.attached_network(), container_network)

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
        docker = docker_api.from_env()

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
        docker = docker_api.from_env()

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
            p.join_sawtooth(committee_ips)

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

        # give the genesis block some time to get to all peers
        time.sleep(3)

        # makes sure genesis block is in each peer
        for p in peers:
            blocks = p.blocks()['data']
            self.assertEqual(1, len(blocks))

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        ips = [p.ip() for p in peers]
        admin = peers[0].admin_key()  # peer 0 made genesis so it has the admin key make sure all other peers get it
        for p in peers:
            self.assertEqual(admin, p.admin_key())
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
            self.assertEqual(number_of_tx, blockchain_size, p.ip())

    def test_high_transaction_load(self):
        peers = make_sawtooth_committee(5)
        number_of_tx = 1
        i = 0
        for _ in range(10):  # peers start to drop old blocks at 100
            peers[i].submit_tx('test{}'.format(number_of_tx), '999')

            i = i + 1 if i < (len(peers) - 1) else 0  # cycle peers

            number_of_tx += 1
            time.sleep(1.5)  # prevent DOS attack counter measure

        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test{}'.format(number_of_tx - 1)))
        for p in peers:
            self.assertEqual(number_of_tx, len(p.blocks()['data']))

    def test_fault_tolerance(self):
        peers = make_sawtooth_committee(9)
        number_of_tx = 1  # genesis

        del peers[0]
        peers[0].submit_tx('test', '999')
        number_of_tx += 1
        # can take some time for peers to commit (potentially 5 min for failed leader)
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test{}'.format(number_of_tx - 1),
                                               timeout=VIEW_CHANGE_WAIT_TIME_SEC * len(peers)))
        for p in peers:
            self.assertEqual(number_of_tx, len(p.blocks()['data']), "Peers did not commit tx in time")

        # should fail now
        del peers[:5]
        peers[0].submit_tx('fail', '000')
        time.sleep(VIEW_CHANGE_WAIT_TIME_SEC * len(peers))  # give it plenty of time to be confirmed + 30 for buffer
        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, peers_blockchain, p.ip())

    def test_large_committee(self):

        peers = make_sawtooth_committee(30)
        number_of_tx = 1  # genesis

        peers[0].submit_tx('test', '999')
        number_of_tx += 1
        time.sleep(0.5)

        peers[1].submit_tx('test1', '888')
        number_of_tx += 1
        time.sleep(0.5)

        peers[2].submit_tx('test2', '777')
        number_of_tx += 1

        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test2'))

        for p in peers:
            blocks = p.blocks()['data']
            self.assertEqual(number_of_tx, len(blocks), p.ip())

    def test_concurrent_large_committee(self):
        # if this fails then the following setting may need to be set in /etc/sysctl.conf
        #
        # # Setup DNS threshold for arp
        # net.ipv4.neigh.default.gc_thresh3 = 16384
        # net.ipv4.neigh.default.gc_thresh2 = 8192
        # net.ipv4.neigh.default.gc_thresh1 = 4096
        # this should work if default linux settings are being used
        peers1 = make_sawtooth_committee(30)
        peers2 = make_sawtooth_committee(30)
        number_of_tx = 1  # genesis

        peers1[0].submit_tx('test', '999')
        peers2[0].submit_tx('test', '999')
        number_of_tx += 1
        time.sleep(0.5)

        peers1[1].submit_tx('test1', '888')
        peers2[1].submit_tx('test1', '888')
        number_of_tx += 1
        time.sleep(0.5)

        peers1[2].submit_tx('test2', '777')
        peers2[2].submit_tx('test2', '777')
        number_of_tx += 1

        self.assertTrue(check_for_confirmation(peers1, number_of_tx, 'test2'))
        self.assertTrue(check_for_confirmation(peers2, number_of_tx, 'test2'))
        for p in peers1:
            blocks = p.blocks()['data']
            self.assertEqual(number_of_tx, len(blocks), p.ip())
        for p in peers2:
            blocks = p.blocks()['data']
            self.assertEqual(number_of_tx, len(blocks), p.ip())

    def test_peer_join(self):
        peers = make_sawtooth_committee(7)
        number_of_tx = 1  # genesis
        peers[0].submit_tx('test', '999')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test'))

        peers[1].submit_tx('test1', '888')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test1'))

        peers.append(SawtoothContainer())
        peers[-1].join_sawtooth([p.ip() for p in peers])

        # wait for block catch up
        done = False
        start = time.time()
        while not done:
            if len(peers[-1].blocks()['data']) >= number_of_tx - 1:  # catch up cant get last tx
                done = True
            elif time.time() - start > 30:
                self.fail("New peers block catch up failed")

        peers[0].update_committee([p.val_key() for p in peers])
        number_of_tx += 1  # +1 for membership of new peer
        time.sleep(VIEW_CHANGE_WAIT_TIME_SEC)  # wait in case leader has to change

        # submit new tx with new peer so it can finally match all the others (i.e. has full blockchain)
        peers[2].submit_tx('test2', '777')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test2'))

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        # and make sure they all have the whole blockchain
        ips = [p.ip() for p in peers]
        for p in peers:
            peers_blocks = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, peers_blocks, p.ip())

            peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
            for ip in ips:
                if ip != p.ip():  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # check consensus still works
        peers[-1].submit_tx('test3', '666')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test3'))
        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            self.assertEqual(number_of_tx, peers_blockchain, p.ip())

    def test_committee_growth(self):
        peers = make_sawtooth_committee(7)
        number_of_tx = 1

        peers[0].submit_tx('test', '999')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test', timeout=120))

        peers[1].submit_tx('test1', '888')
        number_of_tx += 1
        self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test1', timeout=120))

        for i in range(13):
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            # wait for blockchain catch up
            done = False
            start = time.time()
            while not done:
                if len(peers[-1].blocks()['data']) >= number_of_tx - 1:  # catch up cant get last tx
                    done = True
                elif time.time() - start > 30:
                    self.fail("New peers block catch up failed")

            peers[i].update_committee([p.val_key() for p in peers])
            self.assertTrue(check_for_confirmation(peers, number_of_tx, timeout=120))
            number_of_tx += 1  # +1 for membership of new peer

            # check consensus still works
            peers[i].submit_tx('test_{}'.format(i), '777')
            number_of_tx += 1
            self.assertTrue(check_for_confirmation(peers, number_of_tx, 'test_{}'.format(i), timeout=120))

            # makes sure all peers are configured to work with each other (this only tests config not connectivity)
            ips = [p.ip() for p in peers]
            for p in peers:
                peers_blocks = len(p.blocks()['data'])
                self.assertGreaterEqual(number_of_tx, peers_blocks)

                peers_config = p.sawtooth_api('http://localhost:8008/peers')['data']
                for ip in ips:
                    if ip != p.ip():  # the peer it's self is not reported in the list
                        self.assertIn("tcp://{}:8800".format(ip), peers_config)

    def test_new_peer_replace_old(self):  # make sure that if all original peers crash the committee can proceed
        peers = make_sawtooth_committee(7)
        blockchain_size = 1
        for i in range(13):
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            # wait for blockchain catch up
            done = False
            start = time.time()
            while not done:
                if len(peers[-1].blocks()['data']) >= blockchain_size - 1:  # catch up cant get last tx
                    done = True
                elif time.time() - start > 30:
                    self.fail("New peers block catch up failed")
            peers[i % 4].update_committee([p.val_key() for p in peers])
            self.assertTrue(check_for_confirmation(peers, blockchain_size))
            blockchain_size += 1

        for _ in range(4):
            del peers[0]
        gc.collect()  # make sure that the containers are shutdown

        time.sleep(VIEW_CHANGE_WAIT_TIME_SEC + 30)  # wait for view change (timeout + time to do the view change)
        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        self.assertTrue(check_for_confirmation(peers, blockchain_size, 'test'))

        for p in peers:
            print(p.ip())
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

    def test_peer_leave(self):
        peers = make_sawtooth_committee(8)
        blockchain_size = 1

        old_peer = peers.pop()
        peers[0].update_committee([p.val_key() for p in peers])
        self.assertTrue(check_for_confirmation(peers, blockchain_size))
        blockchain_size += 1

        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

        del old_peer
        gc.collect()  # make sure that the containers are shutdown

        # make sure consensus still works
        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        self.assertTrue(check_for_confirmation(peers, blockchain_size, 'test'))
        for p in peers:
            self.assertEqual('999', p.get_tx('test'))
            self.assertEqual(blockchain_size, len(p.blocks()['data']))

    def test_committee_shrink(self):
        peers = make_sawtooth_committee(15)
        blockchain_size = 1
        for i in range(11):
            old_peer = peers.pop()
            peers[0].update_committee([p.val_key() for p in peers])
            self.assertTrue(check_for_confirmation(peers, blockchain_size))
            blockchain_size += 1
            time.sleep(VIEW_CHANGE_WAIT_TIME_SEC)  # wait for potential view change
            del old_peer
            gc.collect()  # make sure that the containers are shutdown

        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        self.assertTrue(check_for_confirmation(peers, blockchain_size, 'test'))
        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))
            self.assertEqual('999', p.get_tx('test'))

    def test_committee_churn(self):
        self.skipTest("Complete committee churn not supported")
        peers = make_sawtooth_committee(7)
        blockchain_size = 1

        peers[0].submit_tx('start', '1')
        blockchain_size += 1
        self.assertTrue(check_for_confirmation(peers, blockchain_size, 'start'))

        for i in range(7):
            # add new peer
            peers.append(SawtoothContainer())
            peers[-1].join_sawtooth([p.ip() for p in peers])
            # wait for blockchain catch up
            done = False
            start = time.time()
            while not done:
                if len(peers[-1].blocks()['data']) >= blockchain_size - 1:  # catch up cant get last tx
                    done = True
                elif time.time() - start > 30:
                    self.fail("New peers block catch up failed")
            peers[0].update_committee([p.val_key() for p in peers])
            peers[0].submit_tx("update_{}".format(i), 999)
            blockchain_size += 1
            self.assertTrue(check_for_confirmation(peers, blockchain_size, "update_{}".format(i),
                                                   timeout=VIEW_CHANGE_WAIT_TIME_SEC))
            blockchain_size += 1

            for p in peers:
                self.assertEqual(blockchain_size, len(p.blocks()['data']))

            old_peer = peers.pop(0)
            peers[0].update_committee([p.val_key() for p in peers])
            self.assertTrue(check_for_confirmation(peers, blockchain_size))
            blockchain_size += 1

            self.assertTrue(check_for_confirmation(peers, blockchain_size, 'test_{}'.format(i)))
            for p in peers:
                self.assertEqual(blockchain_size, len(p.blocks()['data']))

            del old_peer
            gc.collect()  # make sure that the containers are shutdown

        peers[0].submit_tx('test', '999')
        blockchain_size += 1
        self.assertTrue(check_for_confirmation(peers, blockchain_size, 'test'))
        for p in peers:
            self.assertEqual(blockchain_size, len(p.blocks()['data']))
            self.assertEqual('999', p.get_tx('test'))

    def test_concurrent_committees(self):
        set_a = make_sawtooth_committee(20)
        set_b = make_sawtooth_committee(20)
        tx_a = 'test_a'
        tx_b = 'test_b'
        set_a[0].submit_tx(tx_a, '999')
        set_b[0].submit_tx(tx_b, '888')
        self.assertTrue(check_for_confirmation(set_a, 2, tx_a))
        self.assertTrue(check_for_confirmation(set_b, 2, tx_b))
        for p in set_a:
            self.assertEqual(2, len(p.blocks()['data']))
        for p in set_b:
            self.assertEqual(2, len(p.blocks()['data']))

        set_b[0].submit_tx('test_b_2', '777')
        self.assertTrue(check_for_confirmation(set_b, 3, tx_b))


if __name__ == '__main__':
    unittest.main()
