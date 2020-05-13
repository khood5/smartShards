import unittest
import warnings
import time
import docker as dockerapi
from src.util import stop_all_containers
from src.util import make_intersecting_committees
from src.structures import Transaction


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

    def test_make_intersecting_committees(self):
        number_of_committee = 5
        intersection = 1
        committee_size = (number_of_committee - 1) * intersection

        # test making the following
        # committee id: list of peer indices
        #            0: 1  2  3  4
        #            1: 1  5  6  7
        #            2: 2  5  8  9
        #            3: 3  6  8 10
        #            4: 4  7  9 10
        peers = make_intersecting_committees(number_of_committee, intersection)

        # instance is only in a peer once (i.e peer 1 should have two distinct ips, one for each instance)
        ips = []
        for p in peers:
            ips.append(p.ip(p.committee_id_a))
            ips.append(p.ip(p.committee_id_b))

        while ips:
            ip = ips.pop()
            self.assertNotIn(ip, ips)

        # test that confirmation still happens in one and only one committee at a time
        blockchain_length = 1

        # test committee one
        submitted_committees = []
        blockchain_length += 1

        committee_id = peers[0].committee_id_a
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[0].submit(tx)

        time.sleep(3)
        for p in peers:
            if p.committee_id_a in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_a)))

            if p.committee_id_b in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_b)))

        # test committee two
        committee_id = peers[4].committee_id_a
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[4].submit(tx)
        time.sleep(3)
        for p in peers:
            if p.committee_id_a in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_a)))

            if p.committee_id_b in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_b)))

        # test committee three
        committee_id = peers[4].committee_id_a
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[4].submit(tx)
        time.sleep(3)
        for p in peers:
            if p.committee_id_a in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_a)))

            if p.committee_id_b in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_b)))

        # test committee three
        committee_id = peers[7].committee_id_a
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[7].submit(tx)
        time.sleep(3)
        for p in peers:
            if p.committee_id_a in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_a)))

            if p.committee_id_b in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_b)))

        # test committee four
        committee_id = peers[9].committee_id_a
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[9].submit(tx)
        time.sleep(3)
        for p in peers:
            if p.committee_id_a in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_a)))

            if p.committee_id_b in submitted_committees:
                self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
            else:
                self.assertEqual(blockchain_length - 1, len(p.blocks(p.committee_id_b)))

        # test committee 5
        committee_id = peers[9].committee_id_b
        submitted_committees.append(committee_id)
        tx = Transaction(committee_id)
        tx.key = 'test'
        tx.value = '999'
        peers[9].submit(tx)
        time.sleep(3)

        for p in peers:
            self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_a)))
            self.assertEqual(blockchain_length, len(p.blocks(p.committee_id_b)))
