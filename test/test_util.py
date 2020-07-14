from src.util import stop_all_containers
from src.util import make_intersecting_committees
from src.util import forward
from src.api import create_app
from src.api.constants import QUORUMS, API_IP, QUORUM_ID, PORT, TRANSACTION_VALUE, TRANSACTION_KEY
from src.structures import Transaction
import unittest
from mock import patch
import warnings
import time
import docker as docker_api
import json

TRANSACTION_C_JSON = json.loads(json.dumps({QUORUM_ID: "c",
                                            TRANSACTION_KEY: "test",
                                            TRANSACTION_VALUE: "999"}))


class TestUtilMethods(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = docker_api.from_env()
        if len(docker.containers.list()) != 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        stop_all_containers()

    def test_1_intersection(self):

        # test making the following
        # committee id: list of peer indices
        #            0: 1  2  3  4
        #            1: 1  5  6  7
        #            2: 2  5  8  9
        #            3: 3  6  8 10
        #            4: 4  7  9 10
        number_of_committee = 5
        intersection = 1
        self.validate_committee(number_of_committee, intersection)

    def test_2_intersection(self):
        # test making the following
        # committee id: list of peer indices
        #            0: 1  2  3  4  5  6  7  8
        #            1: 1  2  9 10 11 12 13 14
        #            2: 3  4  9 10 15 16 17 18
        #            3: 5  6 11 12 15 16 19 20
        #            4: 7  8 13 14 17 18 19 20
        number_of_committee = 5
        intersection = 2
        self.validate_committee(number_of_committee, intersection)

    def test_3_intersection(self):
        # test making the following
        # committee id: list of peer indices
        #            0: 1  2  3  4  5  6  7  8  9 10
        #            1: 1  2  3  4  5 11 12 13 14 15
        #            2: 6  7  8  9 10 11 12 13 14 15
        number_of_committee = 3
        intersection = 5
        self.validate_committee(number_of_committee, intersection)

    def validate_committee(self, number_of_committee: int, intersection: int):
        peers = make_intersecting_committees(number_of_committee, intersection)

        # instance is only in a peer once (i.e peer 1 should have two distinct ips, one for each instance)
        ips = []
        for p in peers:
            ips.append(p.ip(p.committee_id_a))
            ips.append(p.ip(p.committee_id_b))

        while ips:
            ip = ips.pop()
            self.assertNotIn(ip, ips)

        committee_ids = []
        for p in peers:
            if p.committee_id_a not in committee_ids:
                committee_ids.append(p.committee_id_a)
            if p.committee_id_b not in committee_ids:
                committee_ids.append(p.committee_id_b)

        # check size of committee
        committee_size = (number_of_committee - 1) * intersection
        for committee_id in committee_ids:
            members = 0
            for p in peers:
                if p.committee_id_a == committee_id:
                    members += 1
                if p.committee_id_b == committee_id:
                    members += 1
            self.assertEqual(committee_size, members)

        # test that confirmation still happens in one and only one committee at a time
        blockchain_length = 1
        # test committee one
        submitted_committees = []
        blockchain_length += 1
        # holds one peer from each committee
        committees = {}
        for p in peers:
            if p.committee_id_a not in committees.keys():
                committees[p.committee_id_a] = p

            if p.committee_id_b not in committees.keys():
                committees[p.committee_id_b] = p

        for committee_id in committees:
            submitted_committees.append(committee_id)
            tx = Transaction(committee_id)
            tx.key = 'test'
            tx.value = '999'
            committees[committee_id].submit(tx)
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

        for p in peers:
            del p

    @patch('requests.post')
    def test_forwarding(self, mock_post):
        # making test app and setting up test envi
        app = create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        app.config[QUORUMS]["a"] = [{API_IP: "192.168.1.200", PORT: "5000", QUORUM_ID: "c"},
                                    {API_IP: "192.168.1.300", PORT: "5000", QUORUM_ID: "d"},
                                    {API_IP: "192.168.1.400", PORT: "5000", QUORUM_ID: "e"}]
        mock_post.return_value = '<Response [200]>'
        forward(app, 'submit/', 'c', TRANSACTION_C_JSON)
        self.assertEqual(2, len(mock_post.call_args))
        self.assertEqual('http://192.168.1.200:5000/submit/', mock_post.call_args[0][0])
        self.assertEqual(TRANSACTION_C_JSON, mock_post.call_args[1]['json'])


if __name__ == '__main__':
    unittest.main()
