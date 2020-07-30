from src.Intersection import Intersection
from src.SawtoothPBFT import SawtoothContainer, DEFAULT_DOCKER_NETWORK
from src.util import make_sawtooth_committee
from src.util import stop_all_containers
from src.util import check_for_confirmation
from src.structures import Transaction
import docker as docker_api
import time
import unittest
import warnings
import gc


# makes 2 quorums each with size number of intersections (with whole committee intersection i.e. each peer is in both
# quorums)
def make_peer_committees(size: int, id_a=1, id_b=2):
    containers_a = make_sawtooth_committee(size)
    containers_b = make_sawtooth_committee(size)
    intersections = [Intersection(containers_a[i], containers_b[i], id_a, id_b) for i in range(size)]

    return intersections


class TestIntersectionMethods(unittest.TestCase):

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

    def test_peer_setup(self):
        a = SawtoothContainer()
        b = SawtoothContainer()
        id_a = '1'
        id_b = '2'
        inter = Intersection(a, b, id_a, id_b)

        self.assertEqual(inter.committee_id_a, id_a)
        self.assertEqual(inter.committee_id_b, id_b)
        self.assertEqual(inter.ip(id_a), a.ip())
        self.assertEqual(inter.ip(id_b), b.ip())
        self.assertEqual(inter.attached_network(), DEFAULT_DOCKER_NETWORK)
        self.assertTrue(inter.in_committee(id_a))
        self.assertTrue(inter.in_committee(id_b))
        self.assertFalse(inter.in_committee('c'))
        self.assertFalse(inter.in_committee(0))

        del a, b, inter
        a = SawtoothContainer('host')
        b = SawtoothContainer('host')
        id_a = '1'
        id_b = '2'
        inter = Intersection(a, b, id_a, id_b)
        self.assertEqual(inter.attached_network(), 'host')

    def test_committee_setup_single(self):
        id_a = '1'
        id_b = '2'

        containers_a = [SawtoothContainer() for _ in range(4)]
        user_keys_a = [i.user_key() for i in containers_a]
        val_keys_a = [i.val_key() for i in containers_a]
        committee_ips_a = [i.ip() for i in containers_a]

        containers_b = [SawtoothContainer() for _ in range(4)]
        user_keys_b = [i.user_key() for i in containers_b]
        val_keys_b = [i.val_key() for i in containers_b]
        committee_ips_b = [i.ip() for i in containers_b]

        intersections = [Intersection(containers_a[i], containers_b[i], id_a, id_b) for i in range(4)]

        intersections[0].make_genesis(id_a, val_keys_a, user_keys_a)
        intersections[0].make_genesis(id_b, val_keys_b, user_keys_b)

        for inter in intersections:
            inter.start_sawtooth(committee_ips_a, committee_ips_b)

        # make sure genesis is in every peer and that they can communicate with other committee members
        self.assertEqual(len(intersections), 4)
        for inter in intersections:
            self.assertEqual(len(inter.blocks(id_a)), 1)

        for inter in intersections:
            self.assertEqual(len(inter.blocks(id_b)), 1)

        # make sure util func works
        del containers_a
        del containers_b
        intersections = make_peer_committees(4)
        self.assertEqual(len(intersections), 4)
        for inter in intersections:
            self.assertEqual(len(inter.blocks(id_a)), 1)

        for inter in intersections:
            self.assertEqual(len(inter.blocks(id_b)), 1)

    def test_transaction_confirmation(self):
        intersections = make_peer_committees(4)
        id_a = intersections[0].committee_id_a
        id_b = intersections[0].committee_id_b
        number_of_tx = 1
        tx_a = Transaction(id_a, number_of_tx)
        tx_b = Transaction(id_b, number_of_tx)
        tx_a.key = 'A'
        tx_a.value = '999'
        tx_b.key = 'B'
        tx_b.value = '888'
        intersections[0].submit(tx_a)
        intersections[0].submit(tx_b)
        number_of_tx += 1
        time.sleep(3)  # make sure TX has time to be confirmed
        for inter in intersections:
            a_blocks = len(inter.blocks(id_a))
            b_blocks = len(inter.blocks(id_b))

            self.assertEqual(number_of_tx, a_blocks)
            self.assertEqual(number_of_tx, b_blocks)

        # confirm that the same tx name and value do not collied with different committees
        tx_a = Transaction(id_a, number_of_tx)
        tx_b = Transaction(id_b, number_of_tx)
        tx_a.key = 'test'
        tx_a.value = '777'
        tx_b.key = tx_a.key
        tx_b.value = tx_a.value
        intersections[0].submit(tx_a)
        intersections[0].submit(tx_b)
        number_of_tx += 1
        time.sleep(3)  # make sure TX has time to be confirmed
        for inter in intersections:
            a_blocks = len(inter.blocks(id_a))
            b_blocks = len(inter.blocks(id_b))

            self.assertEqual(number_of_tx, a_blocks)
            self.assertEqual(number_of_tx, b_blocks)

    def test_peer_join(self):
        intersections = make_peer_committees(7)
        id_a = intersections[0].committee_id_a
        id_b = intersections[0].committee_id_b

        intersections[0].submit(Transaction(id_a, 'update_a_1', 999))
        number_of_tx = 2
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx, 'update_a_1', ))
        intersections[0].submit(Transaction(id_b, 'update_b_1', 999))
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx, 'update_b_1', ))

        intersections.append(Intersection(SawtoothContainer(), SawtoothContainer(), id_a, id_b))
        committee_ips_a = [inter.instance_a.ip() for inter in intersections]
        committee_ips_b = [inter.instance_b.ip() for inter in intersections]

        intersections[-1].peer_join(id_a, committee_ips_a)
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx - 1))  # catch up
        intersections[0].update_committee(id_a, [inter.instance_a.val_key() for inter in intersections])
        number_of_tx += 1
        intersections[0].submit(Transaction(id_a, 'update_a_2', 888))
        number_of_tx += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx, 'update_a_2'))

        intersections[-1].peer_join(id_b, committee_ips_b)
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx - 1))  # catch up
        intersections[0].update_committee(id_b, [inter.instance_b.val_key() for inter in intersections])
        intersections[0].submit(Transaction(id_b, 'update_b_2', 888))
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx, 'update_b_2'))

        # makes sure all intersections are configured to work with each other (this is not a test of connectivity
        # just config) and make sure they all have the three tx
        for inter in intersections:
            intersections_config = inter.sawtooth_api(id_a, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_a:
                if ip != inter.ip(id_a):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), intersections_config)

            intersections_config = inter.sawtooth_api(id_b, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_b:
                if ip != inter.ip(id_b):
                    self.assertIn("tcp://{}:8800".format(ip), intersections_config)

    # test that peer can leave a committee with cooperatively
    def test_peer_leave(self):
        intersections = make_peer_committees(7)
        number_of_tx = 1
        id_a = intersections[0].committee_id_a
        id_b = intersections[0].committee_id_b
        old_peer = intersections.pop()
        intersections[0].update_committee(id_a, [inter.val_key(id_a) for inter in intersections])
        intersections[0].update_committee(id_b, [inter.val_key(id_b) for inter in intersections])
        number_of_tx += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx))
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx))

        for inter in intersections:
            self.assertEqual(number_of_tx, len(inter.blocks(id_a)))
            self.assertEqual(number_of_tx, len(inter.blocks(id_b)))
        del old_peer

        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test'
        tx_a.value = '999'
        tx_b = Transaction(id_b, 1)
        tx_b.key = 'test'
        tx_b.value = '888'

        # check consensus still works
        intersections[-1].submit(tx_a)
        intersections[-1].submit(tx_b)
        number_of_tx += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx, 'test'))
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx, 'test'))
        for inter in intersections:
            self.assertEqual(number_of_tx, len(inter.blocks(id_a)))
            self.assertEqual(number_of_tx, len(inter.blocks(id_b)))

    # check that consensus in one committee does not effect the other
    def test_committee_independent_confirmation(self):
        intersections = make_peer_committees(5)
        number_of_tx = 1
        id_a = intersections[0].committee_id_a
        id_b = intersections[0].committee_id_b
        number_of_tx_a = number_of_tx
        number_of_tx_b = number_of_tx
        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test2'
        tx_a.value = '999'
        intersections[-1].submit(tx_a)
        number_of_tx_a += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx, 'test2'))
        for inter in intersections:
            a_blocks = len(inter.blocks(id_a))
            b_blocks = len(inter.blocks(id_b))

            self.assertEqual(number_of_tx_a, a_blocks)
            self.assertEqual(number_of_tx_b, b_blocks)

    # test that a peer can join one committee with out effecting the intersecting one (i.e. committees that intersect
    # are not the same size)
    def test_committee_independent_join(self):
        intersections = make_peer_committees(7)
        number_of_tx_a = 1
        id_a = intersections[0].committee_id_a

        new_peer = Intersection(SawtoothContainer(), None, id_a, None)

        committee_ips_a = [inter.ip(id_a) for inter in intersections]
        committee_ips_a.append(new_peer.ip(id_a))

        committee_val_a = [inter.val_key(id_a) for inter in intersections]
        committee_val_a.append(new_peer.val_key(id_a))

        intersections[0].submit(Transaction(id_a, 'update_a_1', 999))
        number_of_tx_a += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx_a, 'update_a_1'))

        new_peer.peer_join(id_a, committee_ips_a)
        intersections[0].update_committee(id_a, committee_val_a)
        number_of_tx_a += 1

        intersections[0].submit(Transaction(id_a, 'update_a_2', 888))
        number_of_tx_a += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx_a, 'update_a_2'))

        # confirm membership
        committee_a = intersections.copy()
        committee_a.append(new_peer)
        self.assertEqual(None, new_peer.committee_id_b)
        for inter in committee_a:
            intersections_config = inter.sawtooth_api(id_a, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_a:
                if ip != inter.ip(id_a):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), intersections_config)
        for inter in committee_a:
            self.assertEqual(number_of_tx_a, len(inter.blocks(id_a)))

        # now committee B
        id_b = intersections[0].committee_id_b
        number_of_tx_b = 1
        new_peer = Intersection(None, SawtoothContainer(), None, id_b)

        committee_ips_b = [inter.ip(id_b) for inter in intersections]
        committee_ips_b.append(new_peer.ip(id_b))

        committee_val_b = [inter.val_key(id_b) for inter in intersections]
        committee_val_b.append(new_peer.val_key(id_b))

        intersections[0].submit(Transaction(id_b, 'update_b_1', 999))
        number_of_tx_b += 1
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx_b, 'update_b_1'))

        new_peer.peer_join(id_b, committee_ips_b)
        intersections[0].update_committee(id_b, committee_val_b)
        number_of_tx_b += 1
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx_b))

        intersections[0].submit(Transaction(id_b, 'update_b_2', 888))
        number_of_tx_b += 1
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx_b, 'update_b_2'))

        # confirm membership
        committee_b = intersections.copy()
        committee_b.append(new_peer)
        for inter in committee_b:
            intersections_config = inter.sawtooth_api(id_b, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_b:
                if ip != inter.ip(id_b):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), intersections_config)
        for inter in committee_b:
            self.assertEqual(number_of_tx_b, len(inter.blocks(id_b)))

    # test that a peer can leave one committee with out effecting the intersecting one (i.e. committees that intersect
    # are not the same size)
    def test_committee_independent_leave(self):
        intersections = make_peer_committees(7)
        number_of_tx_a = 1
        number_of_tx_b = 1
        id_a = intersections[0].committee_id_a
        id_b = intersections[0].committee_id_b

        # we need to drop only one instance make sure other committee is unaffected
        old_instance = intersections[-1].instance_b

        committee_val_b = [inter.val_key(id_b) for inter in intersections[:-1]]

        intersections[0].update_committee(id_b, committee_val_b)
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections], number_of_tx_b))
        number_of_tx_b += 1
        del old_instance
        gc.collect()
        intersections[-1].instance_b = None
        intersections[-1].committee_id_b = None

        tx_a = Transaction(id_a, 1)
        tx_a.key = 'test'
        tx_a.value = '999'
        tx_b = Transaction(id_b, 1)
        tx_b.key = 'test'
        tx_b.value = '888'

        intersections[-1].submit(tx_a)
        number_of_tx_a += 1
        self.assertTrue(check_for_confirmation([i.instance_a for i in intersections], number_of_tx_a, 'test'))
        intersections[0].submit(tx_b)
        number_of_tx_b += 1
        self.assertTrue(check_for_confirmation([i.instance_b for i in intersections[:-1]], number_of_tx_b, 'test'))

        for inter in intersections:
            self.assertEqual(number_of_tx_a, len(inter.blocks(id_a)))

        for inter in intersections[:-1]:
            self.assertEqual(number_of_tx_b, len(inter.blocks(id_b)))

        self.assertEqual(None, intersections[-1].blocks(id_b))

        # confirm membership
        committee_b = intersections.copy()[:-1]
        committee_ips_b = [inter.ip(id_b) for inter in intersections[:-1]]
        for inter in committee_b:
            intersections_config = inter.sawtooth_api(id_b, 'http://localhost:8008/peers')['data']
            for ip in committee_ips_b:
                if ip != inter.ip(id_b):  # the peer it's self is not reported in the list
                    self.assertIn("tcp://{}:8800".format(ip), intersections_config)


if __name__ == '__main__':
    unittest.main()
