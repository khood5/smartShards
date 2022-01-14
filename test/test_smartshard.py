import requests
from src.SmartShardPeer import SmartShardPeer
from src.Intersection import Intersection
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.api.constants import ROUTE_EXECUTED_CORRECTLY, QUORUMS, PBFT_INSTANCES, QUORUM_ID, PORT
from src.util import stop_all_containers, make_intersecting_committees_on_host, check_for_confirmation, find_free_port
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
        peer = SmartShardPeer()
        peer.start(inter)
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

    def test_cooperative_join(self):
        peers = make_intersecting_committees_on_host(5, 1)
        peer_ports = list(peers.keys())

        res = requests.post(f"http://localhost:{peer_ports[0]}/quoruminfo", headers={"Connection":"close"}).json()["neighbors"]
        print("Pre-join:")
        print(res)

        for peer_list in res.values():
            self.assertEqual(len(peer_list), 3)

        new_peer = SmartShardPeer()
        new_peer.join_network(f"localhost:{peer_ports[0]}")

        print("pre in test")
        print(new_peer.inter)
        print(new_peer.app.api.config[PBFT_INSTANCES])

        time.sleep(5)

        print("post in test")
        print(new_peer.inter)
        print(new_peer.app.api.config[PBFT_INSTANCES])

        res = requests.post(f"http://localhost:{peer_ports[0]}/quoruminfo", headers={"Connection":"close"}).json()["neighbors"]
        print("Post-join:")
        print(res)

        for peer_list in res.values():
            self.assertEqual(len(peer_list), 4)
        
    def test_cooperative_join_2(self):
        peers = make_intersecting_committees_on_host(5, 2)
        peer_ports = list(peers.keys())

        new_peer_1 = SmartShardPeer(port=find_free_port())
        new_peer_1.join_network(f"localhost:{peer_ports[0]}")

        time.sleep(5)

        new_peer_2 = SmartShardPeer(port=find_free_port())
        new_peer_2.join_network(f"localhost:{peer_ports[0]}")

        time.sleep(5)

        print(f"new peer 1, port {new_peer_1.port}, is in {new_peer_1.inter.committee_id_a} and {new_peer_1.inter.committee_id_b}")
        print(f"new peer 2, port {new_peer_2.port}, is in {new_peer_2.inter.committee_id_a} and {new_peer_2.inter.committee_id_b}")

        new_peer_1_res = res = requests.post(f"http://localhost:{new_peer_1.port}/quoruminfo", headers={"Connection":"close"}).json()["neighbors"]
        new_peer_2_res = res = requests.post(f"http://localhost:{new_peer_2.port}/quoruminfo", headers={"Connection":"close"}).json()["neighbors"]

        print(f"new peer 1, neighbors are {new_peer_1_res}")
        print(f"new peer 2, neighbors are {new_peer_2_res}")

        for quorum, neighbors in new_peer_1_res.items():
            print(f"peer 1 has {len(neighbors)} API neighbors {neighbors} in quorum {quorum}")
            docker_peers = new_peer_1.inter.get_ips(quorum)
            print(f"peer 1 has {len(docker_peers)} docker peers {docker_peers} in quorum {quorum}")

        for quorum, neighbors in new_peer_2_res.items():
            print(f"peer 2 has {len(neighbors)} API neighbors in quorum {quorum}")
            docker_peers = new_peer_2.inter.get_ips(quorum)
            print(f"peer 2 has {len(docker_peers)} docker peers {docker_peers} in quorum {quorum}")
        
        time.sleep(5)

    def test_cooperative_leave(self):
        num_committees = 8

        # Tracks how many times each individual quorum has lost a peer
        sawtooth_committees_members = {}
        for i in range(0, num_committees):
            sawtooth_committees_members[i] = num_committees - 1

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

        # Make sure all neighbors know about the leaving peer before they leave
        ids_found = 0
        for search_committee in rand_peer_quorums:
            for port in list(peers.keys()):
                for quorum_id in peers[port].app.api.config[QUORUMS]:
                    for neighbor in peers[port].app.api.config[QUORUMS][quorum_id]:
                        if neighbor[QUORUM_ID] == search_committee:
                            ids_found += 1
                            if ids_found == 2:
                                quorum_exists = True
                                break
        self.assertEqual(True, quorum_exists)

        # Do not allow peers to leave if they should not be allowed to leave
        leave_success = rand_peer.leave()
        if leave_success:
            id_a = peers[rand_port].app.api.config[PBFT_INSTANCES].committee_id_a
            id_b = peers[rand_port].app.api.config[PBFT_INSTANCES].committee_id_b
            sawtooth_committees_members[int(id_a)] -= 1
            sawtooth_committees_members[int(id_b)] -= 1

            del peers[rand_port]
            # Delay to allow other peers to cat ch up
            time.sleep(2)
        else:
            # Peer failed to cooperatively leave
            return

        # Random peer should no longer be running
        running_processes_after_leave = []
        for p in psutil.process_iter():
            running_processes_after_leave.append(p.pid)

        # Leaving API process has been terminated
        self.assertNotIn(rand_peer_pid, running_processes_after_leave)

        # Terminated port is no longer present
        port_found = False
        peer_found = False
        for search_committee in rand_peer_quorums:
            for port in list(peers.keys()):
                for quorum_id in peers[port].app.api.config[QUORUMS]:
                    for neighbor in peers[port].app.api.config[QUORUMS][quorum_id]:
                        if neighbor[PORT] == rand_port:
                            port_found = True
                            break
                        neighbor_inter = peers[port].app.api.config[PBFT_INSTANCES]
                        neighbor_instance_a = neighbor_inter.instance_a
                        neighbor_instance_b = neighbor_inter.instance_b
                        
        # Leaving API process has been removed from peers dict
        self.assertEqual(False, port_found)

        # Continue deleting peers until at breaking point of consensus
        while True:
            random.seed(time.gmtime())
            rand_port = random.choice(list(peers.keys()))
            rand_peer = peers[rand_port]
            rand_inter = rand_peer.app.api.config[PBFT_INSTANCES]

            id_a = rand_inter.committee_id_a
            id_b = rand_inter.committee_id_b

            leave_success = rand_peer.leave()
            del peers[rand_port]
            sawtooth_committees_members[int(id_a)] -= 1
            sawtooth_committees_members[int(id_b)] -= 1

            if sawtooth_committees_members[int(id_a)] >= 4 and sawtooth_committees_members[int(id_b)] >= 4:
                self.assertEqual(True, leave_success)
            else:
                self.assertEqual(False, leave_success)
                return