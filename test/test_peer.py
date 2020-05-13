from src.Peer import Peer
from src.SawtoothPBFT import SawtoothContainer
from src.util import make_peer_committees
from src.util import stop_all_containers
from src.structures import Transaction
import docker as dockerapi
import time
import unittest
import warnings


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

    def test_peer_setup(self):
        a = SawtoothContainer()
        b = SawtoothContainer()
        id_a = 1
        id_b = 2
        p = Peer(a, b, id_a, id_b)

        self.assertEqual(p.neighbors, [])
        self.assertEqual(p.committee_id_a, id_a)
        self.assertEqual(p.committee_id_b, id_b)
        self.assertEqual(p.ip(id_a), a.ip())
        self.assertEqual(p.ip(id_b), b.ip())

    def test_committee_setup_single(self):
        id_a = 1
        id_b = 2

        containers_a = [SawtoothContainer() for _ in range(4)]
        user_keys_a = [i.user_key() for i in containers_a]
        val_keys_a = [i.val_key() for i in containers_a]
        committee_ips_a = [i.ip() for i in containers_a]

        containers_b = [SawtoothContainer() for _ in range(4)]
        user_keys_b = [i.user_key() for i in containers_b]
        val_keys_b = [i.val_key() for i in containers_b]
        committee_ips_b = [i.ip() for i in containers_b]

        peers = [Peer(containers_a[i], containers_b[i], id_a, id_b) for i in range(4)]

        peers[0].make_genesis(id_a, val_keys_a, user_keys_a)
        peers[0].make_genesis(id_b, val_keys_b, user_keys_b)

        for p in peers:
            p.start_sawtooth(committee_ips_a, committee_ips_b)

        # make sure genesis is in every peer and that they can communicate with other committee members
        self.assertEqual(len(peers), 4)
        for p in peers:
            self.assertEqual(len(p.blocks(id_a)), 1)

        for p in peers:
            self.assertEqual(len(p.blocks(id_b)), 1)

        # make sure util func works
        del containers_a
        del containers_b
        peers = make_peer_committees(4)
        self.assertEqual(len(peers), 4)
        for p in peers:
            self.assertEqual(len(p.blocks(id_a)), 1)

        for p in peers:
            self.assertEqual(len(p.blocks(id_b)), 1)

    def test_transaction_confirmation(self):
        peers = make_peer_committees(4)
        id_a = peers[0].committee_id_a
        id_b = peers[0].committee_id_b
        number_of_tx = 1
        tx_a = Transaction(id_a, number_of_tx)
        tx_b = Transaction(id_b, number_of_tx)
        tx_a.key = 'A'
        tx_a.value = '999'
        tx_b.key = 'B'
        tx_b.value = '888'
        peers[0].submit(tx_a)
        peers[0].submit(tx_b)
        number_of_tx += 1
        time.sleep(3)  # make sure TX has time to be confirmed
        for p in peers:
            a_blocks = len(p.blocks(id_a))
            b_blocks = len(p.blocks(id_b))

            self.assertEqual(number_of_tx, a_blocks)
            self.assertEqual(number_of_tx, b_blocks)

        # confirm that the same tx name and value do not collied with different committees
        tx_a = Transaction(id_a, number_of_tx)
        tx_b = Transaction(id_b, number_of_tx)
        tx_a.key = 'test'
        tx_a.value = '777'
        tx_b.key = tx_a.key
        tx_b.value = tx_a.value
        peers[0].submit(tx_a)
        peers[0].submit(tx_b)
        number_of_tx += 1
        time.sleep(3)  # make sure TX has time to be confirmed
        for p in peers:
            a_blocks = len(p.blocks(id_a))
            b_blocks = len(p.blocks(id_b))

            self.assertEqual(number_of_tx, a_blocks)
            self.assertEqual(number_of_tx, b_blocks)

    def test_peer_join(self):
        peers = make_peer_committees(4)
        number_of_tx = 1
        id_a = peers[0].committee_id_a
        id_b = peers[0].committee_id_b
        peers.append(Peer(SawtoothContainer(), SawtoothContainer(), id_a, id_b))
        committee_ips_a = [p.__instance_a.ip() for p in peers]
        committee_ips_b = [p.__instance_b.ip() for p in peers]

        peers[-1].peer_join(id_a, committee_ips_a)
        peers[0].update_committee(id_a, [p.__instance_a.val_key() for p in peers],
                                  [p.__instance_a.user_key() for p in peers])

        peers[-1].peer_join(id_b, committee_ips_b)
        peers[0].update_committee(id_b, [p.__instance_b.val_key() for p in peers],
                                  [p.__instance_b.user_key() for p in peers])
        number_of_tx += 2  # two tx added to both committees

        # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
        # and make sure they all have the three tx
        for p in peers:
            peers_config = p.sawtooth_api(id_a, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_a:
                if ip != p.ip(id_a):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

            peers_config = p.sawtooth_api(id_b, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_b:
                if ip != p.ip(id_b):
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)

        # genesis+2 tx added 1 for membership and 1 for admin rights of new peer so length is 3
        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test1'
        tx_a.value = '999'
        tx_b = Transaction(id_b, 1)
        tx_b.key = 'test2'
        tx_b.value = '888'
        number_of_tx += 1

        # check consensus works
        peers[-1].submit(tx_a)
        peers[-1].submit(tx_b)
        time.sleep(3)
        for p in peers:
            a_blocks = len(p.blocks(id_a))
            b_blocks = len(p.blocks(id_b))

            self.assertEqual(number_of_tx, a_blocks)
            self.assertEqual(number_of_tx, b_blocks)

    def test_peer_leave(self):
        peers = make_peer_committees(5)
        number_of_tx = 1
        id_a = peers[0].committee_id_a
        id_b = peers[0].committee_id_b
        old_peer = peers.pop()
        peers[0].update_committee(id_a, [p.val_key(id_a) for p in peers], [p.user_key(id_a) for p in peers])

        peers[0].update_committee(id_b, [p.val_key(id_b) for p in peers], [p.user_key(id_b) for p in peers])
        number_of_tx += 2
        del old_peer

        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test'
        tx_a.value = '999'
        tx_b = Transaction(id_b, 1)
        tx_b.key = 'test'
        tx_b.value = '888'

        # check consensus still works
        peers[-1].submit(tx_a)
        peers[-1].submit(tx_b)
        number_of_tx += 1
        time.sleep(3)
        for p in peers:
            self.assertEqual(number_of_tx, len(p.blocks(id_a)))
            self.assertEqual(number_of_tx, len(p.blocks(id_b)))

    # check that consensus in one committee does not effect the other
    def test_committee_independent_confirmation(self):
        peers = make_peer_committees(4)
        number_of_tx = 1
        id_a = peers[0].committee_id_a
        id_b = peers[0].committee_id_b
        number_of_tx_a = number_of_tx
        number_of_tx_b = number_of_tx
        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test2'
        tx_a.value = '999'
        peers[-1].submit(tx_a)
        number_of_tx_a += 1
        time.sleep(3)
        for p in peers:
            a_blocks = len(p.blocks(id_a))
            b_blocks = len(p.blocks(id_b))

            self.assertEqual(number_of_tx_a, a_blocks)
            self.assertEqual(number_of_tx_b, b_blocks)

    def test_committee_independent_join(self):
        peers = make_peer_committees(4)
        id_a = peers[0].committee_id_a

        new_peer = Peer(SawtoothContainer(), None, id_a, None)

        committee_ips_a = [p.ip(id_a) for p in peers]
        committee_ips_a.append(new_peer.ip(id_a))

        committee_users_a = [p.user_key(id_a) for p in peers]
        committee_users_a.append(new_peer.user_key(id_a))

        committee_val_a = [p.val_key(id_a) for p in peers]
        committee_val_a.append(new_peer.val_key(id_a))

        new_peer.peer_join(id_a, committee_ips_a)
        peers[0].update_committee(id_a, committee_val_a, committee_users_a)

        self.assertEqual(None, new_peer.__instance_b)
        self.assertEqual(None, new_peer.committee_id_b)

        # confirm membership
        committee_a = peers.copy()
        committee_a.append(new_peer)
        number_of_tx_a = 3  # one for genesis two for join
        for p in committee_a:
            peers_config = p.sawtooth_api(id_a, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_a:
                if ip != p.ip(id_a):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)
            self.assertEqual(number_of_tx_a, len(p.blocks(id_a)))

        committee_b = peers
        id_b = committee_b[0].committee_id_b
        committee_ips_b = [p.ip(id_b) for p in committee_b]
        number_of_tx_b = 1  # genesis
        for p in committee_b:
            peers_config = p.sawtooth_api(id_b, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_b:
                if ip != p.ip(id_b):
                    self.assertIn("tcp://{}:8800".format(ip), peers_config)
            self.assertEqual(number_of_tx_b, len(p.blocks(id_b)))

        # test tx confirmation
        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test'
        tx_a.value = '999'
        new_peer.submit(tx_a)
        number_of_tx_a += 1
        time.sleep(3)
        for p in committee_a:
            self.assertEqual(number_of_tx_a, len(p.blocks(id_a)))
        for p in committee_b:
            self.assertEqual(number_of_tx_b, len(p.blocks(id_b)))

    def test_committee_independent_leave(self):
        peers = make_peer_committees(5)
        number_of_tx_a = 1
        number_of_tx_b = 1
        id_a = peers[0].committee_id_a
        id_b = peers[0].committee_id_b

        old_instance = peers[-1].__instance_b  # we need to drop only one instance make sure other committee is unaffected

        committee_val_b = [p.val_key(id_b) for p in peers]
        committee_user_b = [p.user_key(id_b) for p in peers]

        peers[0].update_committee(id_b, committee_val_b, committee_user_b)
        number_of_tx_b += 2
        del old_instance
        peers[-1].__instance_b = None
        peers[-1].committee_id_b = None

        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test'
        tx_a.value = '999'
        tx_b = Transaction(id_b, 1)
        tx_b.key = 'test'
        tx_b.value = '888'

        peers[-1].submit(tx_a)
        number_of_tx_a += 1
        peers[-1].submit(tx_b)  # this should not be accepted
        time.sleep(3)

        for p in peers:
            self.assertEqual(number_of_tx_a, len(p.blocks(id_a)))

        for p in peers[:-1]:
            self.assertEqual(number_of_tx_b, len(p.blocks(id_b)))

        self.assertEqual(None, peers[-1].blocks(id_b))

        peers[0].submit(tx_b)  # this should work
        number_of_tx_b += 1
        time.sleep(3)

        for p in peers[:-1]:
            self.assertEqual(number_of_tx_b, len(p.blocks(id_b)))

        self.assertEqual(None, peers[-1].blocks(id_b))
