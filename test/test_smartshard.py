import requests

from src.SmartShardPeer import SmartShardPeer
from src.Intersection import Intersection
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.api.constants import ROUTE_EXECUTED_CORRECTLY
from src.structures import Transaction
from src.util import stop_all_containers, make_intersecting_committees_on_host
from src.api.api_util import get_plain_text
import docker as docker_api
import warnings
import psutil
import unittest
import time
import gc

from random import seed
from random import random


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
        # set up initial network
        peers = make_intersecting_committees_on_host(5, 1)
        value = 999
        for p in peers:
            # Confirm some initial transactions
            submit_to = p
            committee_id = peers[submit_to].committee_id_a()
            tx = Transaction(quorum=committee_id, key="test_{}".format(value), value=str(value))
            url = "http://localhost:{port}/submit/".format(port=peers[submit_to].port)
            result = requests.post(url, json=tx.to_json())
            self.assertEqual(ROUTE_EXECUTED_CORRECTLY, get_plain_text(result))
            time.sleep(3)  # wait for network to confirm

        # pick a random peer to notify of join
        seed(gmtime())
        randPeer = peers[random()]

