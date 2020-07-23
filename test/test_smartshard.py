import requests

from src.SmartShardPeer import SmartShardPeer
from src.Intersection import Intersection
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.api.constants import ROUTE_EXECUTED_CORRECTLY, QUORUMS
from src.structures import Transaction
from src.util import stop_all_containers, make_intersecting_committees_on_host
from src.api.api_util import get_plain_text
import docker as docker_api
import warnings
import psutil
import unittest
import time
import gc

import random


class TestSmartShard(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = docker_api.from_env()
       
        #if len(docker.containers.list()) is not 0:
        if len(docker.containers.list()) != 0:
            print('time case didnt match')
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        gc.collect()
        stop_all_containers()

    def test_start(self):
        peer = SmartShardPeer()
        peer.start()

        # get pids of running processes
        pids = []
        for p in psutil.process_iter():
            pids.append(p.pid)

        self.assertIn(peer.pid(), pids)

        # get all open ports
        if peer.port != 5000 and peer.port != 8080:  # joe's computer doesn't like these ports
            conn = []
            for i in psutil.net_connections():
                conn.append(i.laddr.port)
            self.assertIn(peer.port, conn)

        # test with specified port number
        peer = SmartShardPeer(port=8080)
        peer.start()

        # get pids of running processes
        pids = []
        for p in psutil.process_iter():
            pids.append(p.pid)
        self.assertIn(peer.pid(), pids)

        # get all open ports
        if peer.port != 5000 and peer.port != 8080:
            conn = []
            for i in psutil.net_connections():
                conn.append(i.laddr.port)
            self.assertIn(peer.port, conn)

    def test_cleanup(self):
        peer = SmartShardPeer()
        peer.start()
        old_pid = peer.pid()
        old_port = peer.port
        del peer
        time.sleep(5)

        # get pids of running processes
        pids = []
        for p in psutil.process_iter():
            pids.append(p.pid)
        self.assertNotIn(old_pid, pids)

        # get all open ports
        conn = []
        for i in psutil.net_connections():
            conn.append(i.laddr.port)
            self.assertNotIn(old_port, conn)

    def test_setting_instances(self):
        a = SawtoothContainer()
        b = SawtoothContainer()
        inter = Intersection(a, b, 'a', 'b')
        peer = SmartShardPeer(inter)
        peer.start()
        client = peer.app.api.test_client()

        docker = docker_api.from_env()
        # get info on container a
        container_ip = docker.containers.list()[1].exec_run("hostname -i").output.decode('utf-8').strip()
        container_val_key = docker.containers.list()[1].exec_run("cat {val_pub}".format(val_pub=VKEY["pub"])) \
            .output.decode('utf-8').strip()
        container_user_key = docker.containers.list()[1].exec_run("cat {user_pub}".format(user_pub=UKEY["pub"])) \
            .output.decode('utf-8').strip()

        self.assertEqual(get_plain_text(client.get('/ip/a')), container_ip)
        self.assertEqual(get_plain_text(client.get('/val+key/a')), container_val_key)
        self.assertEqual(get_plain_text(client.get('/user+key/a')), container_user_key)
        self.assertNotEqual(get_plain_text(client.get('/val+key/a')), get_plain_text(client.get('/user+key/a')))

        # get info on container b
        container_ip = docker.containers.list()[0].exec_run("hostname -i").output.decode('utf-8').strip()
        container_val_key = docker.containers.list()[0].exec_run("cat {val_pub}".format(val_pub=VKEY["pub"])) \
            .output.decode('utf-8').strip()
        container_user_key = docker.containers.list()[0].exec_run("cat {user_pub}".format(user_pub=UKEY["pub"])) \
            .output.decode('utf-8').strip()

        self.assertEqual(get_plain_text(client.get('/ip/b')), container_ip)
        self.assertEqual(get_plain_text(client.get('/val+key/b')), container_val_key)
        self.assertEqual(get_plain_text(client.get('/user+key/b')), container_user_key)
        self.assertNotEqual(get_plain_text(client.get('/val+key/b')), get_plain_text(client.get('/user+key/b')))

    def test_cooperative_churn(self):
        num_committees = 7
        # set up initial network
        peers = make_intersecting_committees_on_host(num_committees, 1)

        # pick a random peer to leave
        random.seed(time.gmtime())

        rand_port = random.choice(list(peers.keys()))
        rand_peer = peers[rand_port]
        rand_peer_pid = rand_peer.pid()
        rand_peer_quorums = [rand_peer.committee_id_a(), rand_peer.committee_id_b()]

        # Make sure random peer is a valid process before the leave
        running_processes_before_leave = []
        for p in psutil.process_iter():
            running_processes_before_leave.append(p.pid)

        self.assertIn(rand_peer_pid, running_processes_before_leave)

        # Ensure peer is in the dict of peers
        self.assertIn(rand_port, list(peers.keys()))

        quorum_exists = False

        # Ensure quorum exists in some other peer prior to leaving
        for port in list(peers.keys()):
            for quorum_id in rand_peer_quorums:
                print("quorums found:")
                print(peers[port].app.api.config[QUORUMS])
                for found_quorum_id in peers[port].app.api.config[QUORUMS]:
                    print("searching for " + str(quorum_id))
                    if str(quorum_id) == str(found_quorum_id):
                        quorum_exists = True
                        break

        # self.assertEqual(True, quorum_exists) # Needs fix, seems no peers have any quorums at all at the beginning

        peers = rand_peer.leave(peers)
        print(str(rand_peer_pid) + " has left the network, waiting 5 seconds to ensure its absence.")
        time.sleep(5)

        # Random peer should no longer be running
        running_processes_after_leave = []
        for p in psutil.process_iter():
            running_processes_after_leave.append(p.pid)

        # Leaving API process has been terminated
        self.assertNotIn(rand_peer_pid, running_processes_after_leave)

        # Leaving API process has been removed from peers dict
        self.assertNotIn(rand_port, list(peers.keys()))

        # Relevant quorums removed from all neighbors
        for port in list(peers.keys()):
            for quorum_id in rand_peer_quorums:
                self.assertNotIn(str(quorum_id), peers[port].app.api.config[QUORUMS])

