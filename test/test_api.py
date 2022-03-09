import src.api as api
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.api.constants import PBFT_INSTANCES, QUORUMS, QUORUM_ID, QUORUM_IDS, TRANSACTION_KEY, TRANSACTION_VALUE, NEIGHBOURS, API_IP, ROUTE_EXECUTED_CORRECTLY
from src.api.constants import PORT, USER_KEY, VALIDATOR_KEY, DOCKER_IP
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.util import stop_all_containers, make_intersecting_committees_on_host, find_free_port
from src.api.api_util import get_plain_text, create_intersection_map, merge_intersection_maps, insert_into_intersection_map
from src.SmartShardPeer import SmartShardPeer
import docker as docker_api
import unittest
import json
import warnings
import time
import gc
from mock import patch, Mock, MagicMock
from requests import Response
import requests

TRANSACTION_A_JSON = json.loads(json.dumps({QUORUM_ID: "a",
                                            TRANSACTION_KEY: "test",
                                            TRANSACTION_VALUE: "999"}))

TRANSACTION_C_JSON = json.loads(json.dumps({QUORUM_ID: "c",
                                            TRANSACTION_KEY: "test",
                                            TRANSACTION_VALUE: "999"}))

JOIN_A_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.200",  # ip for the API
            DOCKER_IP: "10.10.10.1",  # ip of the container in quorum 'a'
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.300",
            DOCKER_IP: "10.10.10.2",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.400",
            DOCKER_IP: "10.10.10.3",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_A_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.200",  # ip for the API
            DOCKER_IP: "10.10.10.2",
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.300",
            DOCKER_IP: "10.10.10.3",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.400",
            DOCKER_IP: "10.10.10.4",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_B_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.500",  # ip for the API
            DOCKER_IP: "10.10.10.5",
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.600",
            DOCKER_IP: "10.10.10.6",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.700",
            DOCKER_IP: "10.10.10.7",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_C_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.200",  # ip for the API
            DOCKER_IP: "10.10.10.2",
            PORT: "5000",
            QUORUM_ID: "a"
        },
        {
            API_IP: "192.168.1.500",
            DOCKER_IP: "10.10.10.5",
            PORT: "5000",
            QUORUM_ID: "b"
        },
        {
            API_IP: "192.168.1.800",
            DOCKER_IP: "10.10.10.8",
            PORT: "5000",
            QUORUM_ID: "d"
        }
    ]
}))

ADD_D_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.300",  # ip for the API
            DOCKER_IP: "10.10.10.3",
            PORT: "5000",
            QUORUM_ID: "a"
        },
        {
            API_IP: "192.168.1.600",
            DOCKER_IP: "10.10.10.6",
            PORT: "5000",
            QUORUM_ID: "b"
        },
        {
            API_IP: "192.168.1.800",
            DOCKER_IP: "10.10.10.8",
            PORT: "5000",
            QUORUM_ID: "c"
        }
    ]
}))

ADD_A_JSON_MISSING_A_C = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.300",
            DOCKER_IP: "10.10.10.3",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.400",
            DOCKER_IP: "10.10.10.4",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_B_JSON_MISSING_B_D = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.500",  # ip for the API
            DOCKER_IP: "10.10.10.5",
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.700",
            DOCKER_IP: "10.10.10.7",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

MAKE_GENESIS_JSON = json.loads(json.dumps({
    USER_KEY: ["U_key1", "U_key2", "U_key3"],
    VALIDATOR_KEY: ["VAL_key1", "VAL_key2", "VAL_key3"]
}))


class TestAPI(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = docker_api.from_env()
        if len(docker.containers.list()) != 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        stop_all_containers()
        gc.collect()

    def test_api_start(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()

        # test that wrong url do nothing
        response = client.get('/start/')
        self.assertEqual(404, response.status_code)
        self.assertIsNone(app.config[PBFT_INSTANCES])
        self.assertEqual({}, app.config[QUORUMS])
        response = client.get('/start/a/')
        self.assertEqual(404, response.status_code)
        self.assertIsNone(app.config[PBFT_INSTANCES])
        self.assertEqual({}, app.config[QUORUMS])

        # test actual url works
        response = client.get('/start/a/b')
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(app.config[PBFT_INSTANCES])
        self.assertEqual({'a': [], 'b': []}, app.config[QUORUMS])
        docker = docker_api.from_env()
        self.assertEqual(2, len(docker.containers.list()))

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

    def test_start_with_peer(self):
        a = SawtoothContainer()
        b = SawtoothContainer()
        id_a = 'a'
        id_b = 'b'
        p = Intersection(a, b, id_a, id_b)

        app = api.create_app(p)
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()

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

    def test_api_join(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        response = client.post('/join/a', json=JOIN_A_JSON)
        self.assertEqual(200, response.status_code)
        self.assertEqual([
            {
                API_IP: "192.168.1.200",
                DOCKER_IP: "10.10.10.1",
                PORT: "5000",
                QUORUM_ID: "c"
            },
            {
                API_IP: "192.168.1.300",
                DOCKER_IP: "10.10.10.2",
                PORT: "5000",
                QUORUM_ID: "d"
            },
            {
                API_IP: "192.168.1.400",
                DOCKER_IP: "10.10.10.3",
                PORT: "5000",
                QUORUM_ID: "e"
            }
        ], app.config[QUORUMS]["a"])

        self.assertEqual(app.config[QUORUMS]["b"], [])

    def test_add(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        response = client.post('/add/a', json=ADD_A_JSON)
        self.assertEqual(200, response.status_code)
        self.assertEqual([
            {
                DOCKER_IP: "10.10.10.2",
                API_IP: "192.168.1.200",
                PORT: "5000",
                QUORUM_ID: "c"
            },
            {
                DOCKER_IP: "10.10.10.3",
                API_IP: "192.168.1.300",
                PORT: "5000",
                QUORUM_ID: "d"
            },
            {
                DOCKER_IP: "10.10.10.4",
                API_IP: "192.168.1.400",
                PORT: "5000",
                QUORUM_ID: "e"
            }
        ], app.config[QUORUMS]["a"])

        self.assertEqual(app.config[QUORUMS]["b"], [])

    def test_make_genesis(self):
        peer_api_one = api.create_app()
        peer_api_one.config['TESTING'] = True
        peer_api_one.config['DEBUG'] = False
        peer_api_two = api.create_app()
        peer_api_two.config['TESTING'] = True
        peer_api_two.config['DEBUG'] = False
        peer_api_three = api.create_app()
        peer_api_three.config['TESTING'] = True
        peer_api_three.config['DEBUG'] = False
        peer_api_four = api.create_app()
        peer_api_four.config['TESTING'] = True
        peer_api_four.config['DEBUG'] = False

        peers = [peer_api_one.test_client(), peer_api_two.test_client(),
                 peer_api_three.test_client(), peer_api_four.test_client()]

        peers[0].get('/start/a/b')
        peers[1].get('/start/a/c')
        peers[2].get('/start/a/d')
        peers[3].get('/start/a/e')
        docker = docker_api.from_env()
        self.assertEqual(8, len(docker.containers.list()))

        val_keys = [get_plain_text(p.get('/val+key/a')) for p in peers]
        usr_keys = [get_plain_text(p.get('/user+key/a')) for p in peers]

        genesis_json = json.loads(json.dumps({
            USER_KEY: usr_keys,
            VALIDATOR_KEY: val_keys
        }))

        peers[0].post('/make+genesis/a', json=genesis_json)

        pbft_settings = docker.containers.list()[-1].exec_run("ls pbft-settings.batch").output.decode('utf-8').strip()
        config_consensus = docker.containers.list()[-1].exec_run("ls config-consensus.batch").output.decode(
            'utf-8').strip()
        config_genesis = docker.containers.list()[-1].exec_run("ls config-genesis.batch").output.decode('utf-8').strip()

        self.assertEqual('pbft-settings.batch', pbft_settings)
        self.assertEqual('config-consensus.batch', config_consensus)
        self.assertEqual('config-genesis.batch', config_genesis)

    def test_start_committee(self):
        peer_api_one = api.create_app()
        peer_api_one.config['TESTING'] = True
        peer_api_one.config['DEBUG'] = False
        peer_api_two = api.create_app()
        peer_api_two.config['TESTING'] = True
        peer_api_two.config['DEBUG'] = False
        peer_api_three = api.create_app()
        peer_api_three.config['TESTING'] = True
        peer_api_three.config['DEBUG'] = False
        peer_api_four = api.create_app()
        peer_api_four.config['TESTING'] = True
        peer_api_four.config['DEBUG'] = False

        peers = [peer_api_one.test_client(), peer_api_two.test_client(),
                 peer_api_three.test_client(), peer_api_four.test_client()]

        peers[0].get('/start/a/b')
        peers[1].get('/start/a/c')
        peers[2].get('/start/a/d')
        peers[3].get('/start/a/e')
        docker = docker_api.from_env()
        self.assertEqual(8, len(docker.containers.list()))

        val_keys = [get_plain_text(p.get('/val+key/a')) for p in peers]
        usr_keys = [get_plain_text(p.get('/user+key/a')) for p in peers]

        genesis_json = json.loads(json.dumps({
            USER_KEY: usr_keys,
            VALIDATOR_KEY: val_keys
        }))

        peers[0].post('/make+genesis/a', json=genesis_json)

        join_request_data = {NEIGHBOURS: []}
        ip = 1
        quorum = 'b'
        for p in peers:
            # use pretend API address and ports because app is not actually running
            join_request_data[NEIGHBOURS].append(
                {API_IP: "192.168.1.{}".format(ip), DOCKER_IP: get_plain_text(p.get('/ip/a')),
                 PORT: "5000", QUORUM_ID: quorum})
            ip += 1
            quorum = chr(ord(quorum) + 1)

        data = json.loads(json.dumps(join_request_data))
        for p in peers:
            p.post('/join/a', json=data)

        peers[0].post('/submit', json=TRANSACTION_A_JSON)
        time.sleep(3)

        for p in peers:
            self.assertEqual('999', get_plain_text(p.post('/get', json=TRANSACTION_A_JSON)))
    
    def test_self_info(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        response = client.get('/self+info')
        print(response.json)
        self.assertEqual(200, response.status_code)
        self.assertEqual(['a', 'b'], response.json[QUORUM_IDS])
    
    def test_quorum_info(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        client.post('/join/a', json=JOIN_A_JSON)
        response = client.get('/quorum+info/a')
        self.assertEqual(200, response.status_code)
        self.assertEqual({
            'a': [
                {
                    DOCKER_IP: '10.10.10.1',
                    API_IP: '192.168.1.200',
                    PORT: '5000',
                    QUORUM_ID: 'c'
                }, 
                {
                    DOCKER_IP: '10.10.10.2', 
                    API_IP: '192.168.1.300', 
                    PORT: '5000', 
                    QUORUM_ID: 'd'
                }, 
                {
                    DOCKER_IP: '10.10.10.3', 
                    API_IP: '192.168.1.400', 
                    PORT: '5000', 
                    QUORUM_ID: 'e'
                }, 
                {
                    DOCKER_IP: '172.17.0.2', 
                    API_IP: 'localhost', 
                    PORT: '8000', 
                    QUORUM_ID: 'b'
                }
            ]
        }, response.json)
    
    def test_quorum_info_both(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        client.post('/join/a', json=JOIN_A_JSON)
        response = client.get('/quorum+info')
        self.assertEqual(200, response.status_code)
        self.assertEqual({
            'a': [
                {
                    DOCKER_IP: '10.10.10.1',
                    API_IP: '192.168.1.200',
                    PORT: '5000',
                    QUORUM_ID: 'c'
                }, 
                {
                    DOCKER_IP: '10.10.10.2', 
                    API_IP: '192.168.1.300', 
                    PORT: '5000', 
                    QUORUM_ID: 'd'
                }, 
                {
                    DOCKER_IP: '10.10.10.3', 
                    API_IP: '192.168.1.400', 
                    PORT: '5000', 
                    QUORUM_ID: 'e'
                }, 
                {
                    DOCKER_IP: '172.17.0.2', 
                    API_IP: 'localhost', 
                    PORT: '8000', 
                    QUORUM_ID: 'b'
                }
            ],
            'b': [
                {
                    DOCKER_IP: '172.17.0.3', 
                    API_IP: 'localhost', 
                    PORT: '8000', 
                    QUORUM_ID: 'a'
                }
            ]
        }, response.json)
    
    def test_quorum_no_self(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        client.post('/join/a', json=JOIN_A_JSON)
        response = client.get('/quorum+info/a?include_self=false')
        self.assertEqual(200, response.status_code)
        self.assertEqual({
            'a': [
                {
                    DOCKER_IP: '10.10.10.1',
                    API_IP: '192.168.1.200',
                    PORT: '5000',
                    QUORUM_ID: 'c'
                }, 
                {
                    DOCKER_IP: '10.10.10.2', 
                    API_IP: '192.168.1.300', 
                    PORT: '5000', 
                    QUORUM_ID: 'd'
                }, 
                {
                    DOCKER_IP: '10.10.10.3', 
                    API_IP: '192.168.1.400', 
                    PORT: '5000', 
                    QUORUM_ID: 'e'
                }
            ]
        }, response.json)
    
    def test_quorum_info_no_self_both(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()
        client.get('/start/a/b')
        client.post('/join/a', json=JOIN_A_JSON)
        response = client.get('/quorum+info?include_self=false')
        self.assertEqual(200, response.status_code)
        self.assertEqual({
            'a': [
                {
                    DOCKER_IP: '10.10.10.1',
                    API_IP: '192.168.1.200',
                    PORT: '5000',
                    QUORUM_ID: 'c'
                }, 
                {
                    DOCKER_IP: '10.10.10.2', 
                    API_IP: '192.168.1.300', 
                    PORT: '5000', 
                    QUORUM_ID: 'd'
                }, 
                {
                    DOCKER_IP: '10.10.10.3', 
                    API_IP: '192.168.1.400', 
                    PORT: '5000', 
                    QUORUM_ID: 'e'
                }
            ],
            'b': []
        }, response.json)
    
    def test_intersection_map_utils(self):
        quorum_ids = ['a', 'b', 'c', 'd', 'e']
        intersection_map_1 = create_intersection_map(quorum_ids)
        self.assertEqual(intersection_map_1, {
            'a': {'b': {}, 'c': {}, 'd': {}, 'e': {}},
            'b': {'c': {}, 'd': {}, 'e': {}},
            'c': {'d': {}, 'e': {}},
            'd': {'e': {}},
            'e': {}
        })

        insert_into_intersection_map(intersection_map_1, "test_1", 'a', 'b')
        self.assertEqual(intersection_map_1, {
            'a': {'b': {"test_1": 0}, 'c': {}, 'd': {}, 'e': {}},
            'b': {'c': {}, 'd': {}, 'e': {}},
            'c': {'d': {}, 'e': {}},
            'd': {'e': {}},
            'e': {}
        })

        intersection_map_2 = create_intersection_map(quorum_ids)
        insert_into_intersection_map(intersection_map_2, "test_2", 'c', 'd')
        self.assertEqual(intersection_map_2, {
            'a': {'b': {}, 'c': {}, 'd': {}, 'e': {}},
            'b': {'c': {}, 'd': {}, 'e': {}},
            'c': {'d': {"test_2": 0}, 'e': {}},
            'd': {'e': {}},
            'e': {}
        })

        intersection_map_3 = merge_intersection_maps(intersection_map_1, intersection_map_2)
        self.assertEqual(intersection_map_3, {
            'a': {'b': {"test_1": 0}, 'c': {}, 'd': {}, 'e': {}},
            'b': {'c': {}, 'd': {}, 'e': {}},
            'c': {'d': {"test_2": 0}, 'e': {}},
            'd': {'e': {}},
            'e': {}
        })
    
    def test_intersection_map(self):
        # Create a set of intersecting committees
        peers = make_intersecting_committees_on_host(5, 1)

        # Get the peers ports, and make a request to the 0th peer for the intersection map
        ports = list(peers.keys())
        known_peer = f"localhost:{ports[0]}"
        intersection_map = requests.get(f"http://{known_peer}/intersection+map", headers={"Connection":"close"}).json()
        print(intersection_map)

        # Get the quorums listed in the intersection map, make sure there are 5
        quorums = list(intersection_map.keys())
        self.assertEqual(len(quorums), 5)

        # Go through each intersection and make sure that there is only 1 peer each, 
        # and that the peer's port is in the peers dictionary ports
        for first_quorum, second_quorums in intersection_map.items():
            for second_quorum, intersection_peers in second_quorums.items():
                self.assertEqual(len(intersection_peers), 1)
                for peer in intersection_peers.keys():
                    self.assertIn(int(peer.split(':')[1]), ports)
    
    @patch('requests.get')
    def test_min_intersection_all_equal(self, mock_get):
        # Fully connected, 5 quorums
        # Responses from a-c, a-d, a-e, b-c, b-d, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        res = test_client.get('/min+intersection')
        self.assertEqual(res.get_json(), {'min_intersection': ['a', 'b'], 'peers': {'localhost': 0}})
    
    @patch('requests.get')
    def test_min_intersection_1_less_than_rest(self, mock_get):
        # Almost fully connected, missing A-C peer
        # Responses from a-d, a-e, b-c, b-d, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON_MISSING_A_C)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        res = test_client.get('/min+intersection')
        self.assertEqual(res.get_json(), {'min_intersection': ['a', 'c'], 'peers': {}})
    
    @patch('requests.get')
    def test_min_intersection_2_less_than_rest(self, mock_get):
        # Almost fully connected, missing A-C peer and B-D peer
        # Responses from a-d, a-e, b-c, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON_MISSING_A_C)
        test_client.post('/add/b', json=ADD_B_JSON_MISSING_B_D)
        time.sleep(1)
        res = test_client.get('/min+intersection')
        self.assertEqual(res.get_json(), {'min_intersection': ['a', 'c'], 'peers': {}})

    @patch('requests.get')
    def test_max_intersection_all_equal(self, mock_get):
        # Fully connected, 5 quorums
        # Responses from a-c, a-d, a-e, b-c, b-d, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        res = test_client.get('/max+intersection')
        self.assertEqual(res.get_json(), {'max_intersection': ['a', 'b'], 'peers': {'localhost': 0}})
    
    @patch('requests.get')
    def test_max_intersection_1_more_than_rest(self, mock_get):
        # Fully connected, extra A-C peer
        # Responses from a-c, a-c, a-d, a-e, b-c, b-d, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0, "192.168.1.1100:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON_MISSING_A_C)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        res = test_client.get('/max+intersection')
        self.assertEqual(res.get_json(), {'max_intersection': ['a', 'c'], 'peers': {"192.168.1.200:5000": 0, "192.168.1.1100:5000": 0}})
    
    @patch('requests.get')
    def test_max_intersection_2_more_than_rest(self, mock_get):
        # Fully connected, extra A-C peer and B-D peer
        # Responses from a-c, a-c, a-d, a-e, b-c, b-d, b-d, b-e
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0, "192.168.1.1100:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0, "192.168.1.1200:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}, 'e': {}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.json = MagicMock(return_value=intersection_map)
            res.status_code = 200
            side_effects.append(res)
        mock_get.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON_MISSING_A_C)
        test_client.post('/add/b', json=ADD_B_JSON_MISSING_B_D)
        time.sleep(1)
        res = test_client.get('/max+intersection')
        self.assertEqual(res.get_json(), {'max_intersection': ['a', 'c'], 'peers': {"192.168.1.200:5000": 0, "192.168.1.1100:5000": 0}})
    
    def test_remove_host(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        test_client.post('/remove+host', json={"host": "192.168.1.300:5000"})
        self.assertEqual(
            app.config[QUORUMS]['a'], 
            [
                {
                    DOCKER_IP: "10.10.10.2",
                    API_IP: "192.168.1.200",  # ip for the API
                    PORT: "5000",
                    QUORUM_ID: "c"
                },
                {
                    DOCKER_IP: "10.10.10.4",
                    API_IP: "192.168.1.400",
                    PORT: "5000",
                    QUORUM_ID: "e"
                }
            ]
        )
    
    def test_add_host(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        test_client.get('/start/a/b')
        test_client.post('/add/a', json=ADD_A_JSON)
        test_client.post('/add/b', json=ADD_B_JSON)
        time.sleep(1)
        test_client.post('/add+host', json={"host": "192.168.1.1100:5000", "quorum": "a", "host_quorum": "a", "docker_ip": "10.10.10.11"})
        self.assertEqual(
            app.config[QUORUMS]['a'], 
            [
                {
                    DOCKER_IP: "10.10.10.2",
                    API_IP: "192.168.1.200",  # ip for the API
                    PORT: "5000",
                    QUORUM_ID: "c"
                },
                {
                    DOCKER_IP: "10.10.10.3",
                    API_IP: "192.168.1.300",
                    PORT: "5000",
                    QUORUM_ID: "d"
                },
                {
                    DOCKER_IP: "10.10.10.4",
                    API_IP: "192.168.1.400",
                    PORT: "5000",
                    QUORUM_ID: "e"
                },
                {
                    DOCKER_IP: "10.10.10.11",
                    API_IP: "192.168.1.1100",
                    PORT: "5000",
                    QUORUM_ID: "a"
                }
            ]
        )
    
    def test_remove_add_validator(self):
        peers = make_intersecting_committees_on_host(5, 2)
        ports = list(peers.keys())
        remove_peer = peers[ports[0]]
        known_peer = peers[ports[1]]
        add_peer = SmartShardPeer(find_free_port())
        add_peer.start()
        quorum_id = remove_peer.app.api.config[PBFT_INSTANCES].committee_id_a
        other_quorum_id = remove_peer.app.api.config[PBFT_INSTANCES].committee_id_b

        neighbors = requests.get(f"http://localhost:{known_peer.port}/quorum+info/{quorum_id}").json()

        requests.get(f"http://localhost:{add_peer.port}/start/{quorum_id}/{other_quorum_id}")
        requests.post(f"http://localhost:{add_peer.port}/join/{quorum_id}", json={NEIGHBOURS: neighbors[quorum_id]}, headers={"Connection":"close"})

        requests.post(f"http://localhost:{known_peer.port}/remove+validator", json={
            "quorum_id": quorum_id,
            "val_key": requests.get(f"http://localhost:{remove_peer.port}/val+key/{quorum_id}").text
        }, headers={"Connection":"close"})

        validators = requests.get(f"http://localhost:{known_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 7)

        self.assertNotIn(requests.get(f"http://localhost:{remove_peer.port}/val+key/{quorum_id}").text, validators)

        requests.post(f"http://localhost:{known_peer.port}/add+validator", json={
            "quorum_id": quorum_id,
            "val_key": requests.get(f"http://localhost:{remove_peer.port}/val+key/{quorum_id}").text
        }, headers={"Connection":"close"})

        validators = requests.get(f"http://localhost:{known_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 8)

        self.assertIn(requests.get(f"http://localhost:{remove_peer.port}/val+key/{quorum_id}").text, validators)

        validators = requests.get(f"http://localhost:{remove_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 8)

        self.assertIn(requests.get(f"http://localhost:{remove_peer.port}/val+key/{quorum_id}").text, validators)

        requests.post(f"http://localhost:{known_peer.port}/add+validator", json={
            "quorum_id": quorum_id,
            "val_key": requests.get(f"http://localhost:{add_peer.port}/val+key/{quorum_id}").text
        }, headers={"Connection":"close"})

        validators = requests.get(f"http://localhost:{known_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 9)

        self.assertIn(requests.get(f"http://localhost:{add_peer.port}/val+key/{quorum_id}").text, validators)

        validators = requests.get(f"http://localhost:{add_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 9)

        self.assertIn(requests.get(f"http://localhost:{add_peer.port}/val+key/{quorum_id}").text, validators)

        requests.post(f"http://localhost:{known_peer.port}/remove+validator", json={
            "quorum_id": quorum_id,
            "val_key": requests.get(f"http://localhost:{add_peer.port}/val+key/{quorum_id}").text
        }, headers={"Connection":"close"})

        validators = requests.get(f"http://localhost:{known_peer.port}/committee+val+keys/{quorum_id}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators), 8)

        self.assertNotIn(requests.get(f"http://localhost:{add_peer.port}/val+key/{quorum_id}").text, validators)
    
    def test_request_join(self):
        # Create 5 quorums, 2 peers per intersection, 8 peers per quorum
        peers = make_intersecting_committees_on_host(5, 2)
        port = list(peers.keys())[0]
        known_host = f"localhost:{port}"

        # Figure out the minimum intersection
        min_intersection = requests.get(f"http://{known_host}/min+intersection", headers={"Connection":"close"}).json()
        min_quorums = min_intersection['min_intersection'] # The quorum id's of the min intersection
        min_peers = min_intersection['peers'] # The peers that are in the min intersection
        min_peer = list(min_peers.keys())[0] # The 0th peer in the min intersection
        min_id_a = min_quorums[0] # Should be quorum id 0
        min_id_b = min_quorums[1] # Should be quorum id 1
        self.assertEqual(min_id_a, '0')
        self.assertEqual(min_id_b, '1')

        # Check how many sawtooth validators each min quorum has, should be 8
        validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 8) # 8 in quorum 0
        self.assertEqual(len(validators_b), 8) # 8 in quorum 1

        # Check how many API neighbors each min quorum has, should be 8
        quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a]), 8) # 8 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b]), 8) # 8 in quorum 1

        # Create a new SmartShardPeer object (easier to set up and join)
        peer_1 = SmartShardPeer(port=find_free_port())
        peer_1.start()
        requests.post(f"http://localhost:{peer_1.port}/request+join", json={"known_host": known_host}, headers={"Connection":"close"})

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test1", TRANSACTION_VALUE: "000"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test2", TRANSACTION_VALUE: "001"}, headers={"Connection":"close"})

        time.sleep(10)

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test3", TRANSACTION_VALUE: "002"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test4", TRANSACTION_VALUE: "003"}, headers={"Connection":"close"})

        time.sleep(10)

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test5", TRANSACTION_VALUE: "004"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test6", TRANSACTION_VALUE: "005"}, headers={"Connection":"close"})

        time.sleep(10)

        # Check how many sawtooth validators each min quorum has, should be 9 after peer 1 joins
        validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 9) # 9 in quorum 0
        self.assertEqual(len(validators_b), 9) # 9 in quorum 1

        validators_a_peer_1 = requests.get(f"http://localhost:{peer_1.port}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b_peer_1 = requests.get(f"http://localhost:{peer_1.port}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a_peer_1), 9) # 9 in quorum 0
        self.assertEqual(len(validators_b_peer_1), 9) # 9 in quorum 1

        # Make sure that peer_1's validator keys are in the respective quorums
        peer_1_val_key_a = requests.get(f"http://localhost:{peer_1.port}/val+key/{min_id_a}", headers={"Connection":"close"}).text
        peer_1_val_key_b = requests.get(f"http://localhost:{peer_1.port}/val+key/{min_id_b}", headers={"Connection":"close"}).text
        self.assertIn(peer_1_val_key_a, validators_a)
        self.assertIn(peer_1_val_key_b, validators_b)
        self.assertIn(peer_1_val_key_a, validators_a_peer_1)
        self.assertIn(peer_1_val_key_b, validators_b_peer_1)

        # Check how many API neighbors each min quorum has, should be 9 after peer 1 joins
        quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a]), 9) # 9 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b]), 9) # 9 in quorum 1
        
        # Make sure that peer 1 joined the correct quorums, 0-1
        quorum_info = requests.get(f"http://localhost:{peer_1.port}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(list(quorum_info.keys()), min_quorums)

        # Figure out the new minimum intersection
        min_intersection = requests.get(f"http://{known_host}/min+intersection", headers={"Connection":"close"}).json()
        min_quorums = min_intersection['min_intersection'] # The quorum id's of the min intersection
        min_peers = min_intersection['peers'] # The peers that are in the min intersection
        min_peer = list(min_peers.keys())[0] # The 0th peer in the min intersection
        min_id_a = min_quorums[0] # Should be quorum id 0
        min_id_b = min_quorums[1] # Should be quorum id 2

        # Check how many sawtooth validators each min quorum has, should be 9 and 8
        validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 9) # 9 in quorum 0
        self.assertEqual(len(validators_b), 8) # 8 in quorum 2

        # Check how many API neighbors each min quorum has, should be 9 and 8
        quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a]), 9) # 9 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b]), 8) # 8 in quorum 2

        # Create a new SmartShardPeer object (easier to set up and join)
        peer_2 = SmartShardPeer(port=find_free_port())
        peer_2.start()
        requests.post(f"http://localhost:{peer_2.port}/request+join", json={"known_host": known_host}, headers={"Connection":"close"})

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test7", TRANSACTION_VALUE: "006"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test8", TRANSACTION_VALUE: "007"}, headers={"Connection":"close"})

        time.sleep(10)

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test9", TRANSACTION_VALUE: "008"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test10", TRANSACTION_VALUE: "009"}, headers={"Connection":"close"})

        time.sleep(10)

        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test11", TRANSACTION_VALUE: "010"}, headers={"Connection":"close"})
        requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test12", TRANSACTION_VALUE: "011"}, headers={"Connection":"close"})

        time.sleep(10)

        # Check how many sawtooth validators each min quorum has, should be 10 and 9 after peer 2 joins
        validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 10) # 10 in quorum 0
        self.assertEqual(len(validators_b), 9) # 9 in quorum 2

        validators_a_peer_2 = requests.get(f"http://localhost:{peer_2.port}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b_peer_2 = requests.get(f"http://localhost:{peer_2.port}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a_peer_2), 10) # 10 in quorum 0
        self.assertEqual(len(validators_b_peer_2), 9) # 9 in quorum 2

        # Make sure that peer_2's validator keys are in the respective quorums
        peer_2_val_key_a = requests.get(f"http://localhost:{peer_2.port}/val+key/{min_id_a}", headers={"Connection":"close"}).text
        peer_2_val_key_b = requests.get(f"http://localhost:{peer_2.port}/val+key/{min_id_b}", headers={"Connection":"close"}).text
        self.assertIn(peer_2_val_key_a, validators_a)
        self.assertIn(peer_2_val_key_b, validators_b)
        self.assertIn(peer_2_val_key_a, validators_a_peer_2)
        self.assertIn(peer_2_val_key_b, validators_b_peer_2)

        # Check how many API neighbors each min quorum has, should be 10 and 9 after peer 2 joins
        quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a]), 10) # 10 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b]), 9) # 9 in quorum 2
        
        # Make sure that peer 2 joined the correct quorums, 0-2
        quorum_info = requests.get(f"http://localhost:{peer_2.port}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(list(quorum_info.keys()), min_quorums)
    
    def test_request_join_same(self):
        # Create 2 quorums, 8 peers per intersection, 8 peers per quorum
        peers = make_intersecting_committees_on_host(2, 8)
        port = list(peers.keys())[0]
        known_host = f"localhost:{port}"

        res = requests.get(f"http://localhost:{port}/self+info")
        print(f"peer {0} has self info '{res.json()}'")

        # Figure out the minimum intersection
        min_intersection = requests.get(f"http://{known_host}/min+intersection", headers={"Connection":"close"}).json()
        min_quorums = min_intersection['min_intersection'] # The quorum id's of the min intersection
        min_peers = min_intersection['peers'] # The peers that are in the min intersection
        min_peer = list(min_peers.keys())[0] # The 0th peer in the min intersection
        min_id_a = min_quorums[0] # Should be quorum id 0
        min_id_b = min_quorums[1] # Should be quorum id 1
        self.assertEqual(min_id_a, '0')
        self.assertEqual(min_id_b, '1')

        # Check how many sawtooth validators each min quorum has, should be 8
        validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 8) # 8 in quorum 0
        self.assertEqual(len(validators_b), 8) # 8 in quorum 1

        # Check how many API neighbors each min quorum has, should be 8
        quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a]), 8) # 8 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b]), 8) # 8 in quorum 1

        for i in range(5): # Join 5 new peers

            # Create a new SmartShardPeer object (easier to set up and join)
            new_peer = SmartShardPeer(port=find_free_port())
            new_peer.start()
            requests.post(f"http://localhost:{new_peer.port}/request+join", json={"known_host": known_host}, headers={"Connection":"close"})

            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test1", TRANSACTION_VALUE: "000"}, headers={"Connection":"close"})
            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test2", TRANSACTION_VALUE: "001"}, headers={"Connection":"close"})

            time.sleep(10)

            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test3", TRANSACTION_VALUE: "002"}, headers={"Connection":"close"})
            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test4", TRANSACTION_VALUE: "003"}, headers={"Connection":"close"})

            time.sleep(10)

            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_a, TRANSACTION_KEY: "test5", TRANSACTION_VALUE: "004"}, headers={"Connection":"close"})
            requests.post(f"http://{min_peer}/submit", json={QUORUM_ID: min_id_b, TRANSACTION_KEY: "test6", TRANSACTION_VALUE: "005"}, headers={"Connection":"close"})

            time.sleep(10)

            # Check how many sawtooth validators each min quorum has, should be 9+i after new peer joins
            validators_a = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
            validators_b = requests.get(f"http://{min_peer}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
            self.assertEqual(len(validators_a), 9+i) # 9+i in quorum 0
            self.assertEqual(len(validators_b), 9+i) # 9+i in quorum 1

            validators_a_new_peer = requests.get(f"http://localhost:{new_peer.port}/committee+val+keys/{min_id_a}", headers={"Connection":"close"}).json()
            validators_b_new_peer = requests.get(f"http://localhost:{new_peer.port}/committee+val+keys/{min_id_b}", headers={"Connection":"close"}).json()
            self.assertEqual(len(validators_a_new_peer), 9+i) # 9+i in quorum 0
            self.assertEqual(len(validators_b_new_peer), 9+i) # 9+i in quorum 1

            # Make sure that new peer's validator keys are in the respective quorums
            new_peer_val_key_a = requests.get(f"http://localhost:{new_peer.port}/val+key/{min_id_a}", headers={"Connection":"close"}).text
            new_peer_val_key_b = requests.get(f"http://localhost:{new_peer.port}/val+key/{min_id_b}", headers={"Connection":"close"}).text
            self.assertIn(new_peer_val_key_a, validators_a)
            self.assertIn(new_peer_val_key_b, validators_b)
            self.assertIn(new_peer_val_key_a, validators_a_new_peer)
            self.assertIn(new_peer_val_key_b, validators_b_new_peer)

            # Check how many API neighbors each min quorum has
            quorum_info = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()
            self.assertEqual(len(quorum_info[min_id_a]), 9+i) # 9+i in quorum 0
            self.assertEqual(len(quorum_info[min_id_b]), 9+i) # 9+i in quorum 1
            
            # Make sure that new peer joined the correct quorums, 0-1
            quorum_info = requests.get(f"http://localhost:{new_peer.port}/quorum+info", headers={"Connection":"close"}).json()
            self.assertEqual(list(quorum_info.keys()), min_quorums)

            print(f"{i+1} peers successfully joined")
            res = requests.get(f"http://localhost:{new_peer.port}/self+info")
            print(f"peer {i+1} has self info '{res.json()}'")

            peers[new_peer.port] = new_peer
    
    def test_request_leave(self):
        # Create 5 quorums, 2 peers per intersection, 8 peers per quorum
        peers = make_intersecting_committees_on_host(5, 2)
        known_peer = list(peers.values())[0]

        # Figure out the minimum intersection
        min_intersection_0_1 = requests.get(f"http://localhost:{known_peer.port}/min+intersection", headers={"Connection":"close"}).json()
        min_quorums_0_1 = min_intersection_0_1['min_intersection'] # The quorum id's of the min intersection
        min_peers_0_1 = min_intersection_0_1['peers'] # The peers that are in the min intersection
        min_peer_0_1 = list(min_peers_0_1.keys())[0] # The 0th peer in the min intersection
        min_id_a_0_1 = min_quorums_0_1[0] # Should be quorum id 0
        min_id_b_0_1 = min_quorums_0_1[1] # Should be quorum id 1
        self.assertEqual(min_id_a_0_1, '0')
        self.assertEqual(min_id_b_0_1, '1')

        # Check how many sawtooth validators each min quorum has, should be 8
        validators_a = requests.get(f"http://{min_peer_0_1}/committee+val+keys/{min_id_a_0_1}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer_0_1}/committee+val+keys/{min_id_b_0_1}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 8) # 8 in quorum 0
        self.assertEqual(len(validators_b), 8) # 8 in quorum 1

        # Check how many API neighbors each min quorum has, should be 8
        quorum_info = requests.get(f"http://{min_peer_0_1}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a_0_1]), 8) # 8 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b_0_1]), 8) # 8 in quorum 1

        # Create a new SmartShardPeer object (easier to set up and join)
        join_port = find_free_port()

        print(f"Join port: {join_port}, current peers: {min_peers_0_1}")

        join_peer = SmartShardPeer(join_port)
        join_peer.start()
        requests.post(f"http://localhost:{join_peer.port}/request+join", json={"known_host": f"localhost:{known_peer.port}"}, headers={"Connection":"close"})

        # requests.post(f"http://localhost:{known_peer.port}/submit", json={QUORUM_ID: min_id_a_0_1, TRANSACTION_KEY: "test", TRANSACTION_VALUE: "999"}, headers={"Connection":"close"})
        # requests.post(f"http://localhost:{known_peer.port}/submit", json={QUORUM_ID: min_id_b_0_1, TRANSACTION_KEY: "test", TRANSACTION_VALUE: "999"}, headers={"Connection":"close"})

        # time.sleep(10)

        # Check how many sawtooth validators each min quorum has, should be 9 after peer 1 joins
        validators_a = requests.get(f"http://{min_peer_0_1}/committee+val+keys/{min_id_a_0_1}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{min_peer_0_1}/committee+val+keys/{min_id_b_0_1}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 9) # 9 in quorum 0
        self.assertEqual(len(validators_b), 9) # 9 in quorum 1

        # Make sure that join_peer's validator keys are in the respective quorums
        join_peer_val_key_a = requests.get(f"http://localhost:{join_peer.port}/val+key/{min_id_a_0_1}", headers={"Connection":"close"}).text
        join_peer_val_key_b = requests.get(f"http://localhost:{join_peer.port}/val+key/{min_id_b_0_1}", headers={"Connection":"close"}).text
        self.assertIn(join_peer_val_key_a, validators_a)
        self.assertIn(join_peer_val_key_b, validators_b)

        # Check how many sawtooth validators each min quorum has, should be 9 after peer 1 joins
        validators_a = requests.get(f"http://localhost:{join_peer.port}/committee+val+keys/{min_id_a_0_1}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://localhost:{join_peer.port}/committee+val+keys/{min_id_b_0_1}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 9) # 9 in quorum 0
        self.assertEqual(len(validators_b), 9) # 9 in quorum 1

        # Make sure that join_peer's validator keys are in the respective quorums
        join_peer_val_key_a = requests.get(f"http://localhost:{join_peer.port}/val+key/{min_id_a_0_1}", headers={"Connection":"close"}).text
        join_peer_val_key_b = requests.get(f"http://localhost:{join_peer.port}/val+key/{min_id_b_0_1}", headers={"Connection":"close"}).text
        self.assertIn(join_peer_val_key_a, validators_a)
        self.assertIn(join_peer_val_key_b, validators_b)

        # Check how many API neighbors each min quorum has, should be 9 after join_peer joins
        quorum_info = requests.get(f"http://{min_peer_0_1}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a_0_1]), 9) # 9 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b_0_1]), 9) # 9 in quorum 1
        
        # Make sure that join_peer joined the correct quorums, 0-1
        quorum_info = requests.get(f"http://localhost:{join_peer.port}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(list(quorum_info.keys()), min_quorums_0_1)

        # Figure out the new maximum intersection
        max_intersection_0_1 = requests.get(f"http://localhost:{known_peer.port}/max+intersection", headers={"Connection":"close"}).json()
        max_quorums_0_1 = max_intersection_0_1['max_intersection'] # The quorum id's of the max intersection
        max_peers_0_1 = max_intersection_0_1['peers'] # The peers that are in the max intersection
        replacement_peer_0_1 = list(max_peers_0_1.keys())[0] # The replacement peer in the max intersection
        stay_peer_0_1 = list(max_peers_0_1.keys())[1] # The replacement peer in the max intersection
        max_id_a_0_1 = max_quorums_0_1[0] # Should be quorum id 0
        max_id_b_0_1 = max_quorums_0_1[1] # Should be quorum id 2
        self.assertEqual(max_id_a_0_1, '0')
        self.assertEqual(max_id_b_0_1, '1')

        # Figure out the new minimum intersection
        min_intersection_0_2 = requests.get(f"http://localhost:{known_peer.port}/min+intersection", headers={"Connection":"close"}).json()
        min_quorums_0_2 = min_intersection_0_2['min_intersection'] # The quorum id's of the min intersection
        min_peers_0_2 = min_intersection_0_2['peers'] # The peers that are in the min intersection
        min_peer_0_2 = list(min_peers_0_2.keys())[0] # The 0th peer in the min intersection
        min_id_a_0_2 = min_quorums_0_2[0] # Should be quorum id 0
        min_id_b_0_2 = min_quorums_0_2[1] # Should be quorum id 2
        self.assertEqual(min_id_a_0_2, '0')
        self.assertEqual(min_id_b_0_2, '2')

        # A peer in 0-2 wants to leave, should be replaced by a peer in 0-1
        res = requests.post(f"http://{min_peer_0_2}/request+leave", headers={"Connection":"close"})

        # requests.post(f"http://{replacement_peer_0_1}/submit", json={QUORUM_ID: min_id_a_0_2, TRANSACTION_KEY: "test", TRANSACTION_VALUE: "999"}, headers={"Connection":"close"})
        # requests.post(f"http://{replacement_peer_0_1}/submit", json={QUORUM_ID: min_id_b_0_2, TRANSACTION_KEY: "test", TRANSACTION_VALUE: "999"}, headers={"Connection":"close"})

        # time.sleep(10)

        # Check how many sawtooth validators 0 and 1 have, should be 8 after a 0-2 peer leaves and is replaced by a 0-1 peer
        validators_a = requests.get(f"http://{stay_peer_0_1}/committee+val+keys/{min_id_a_0_1}", headers={"Connection":"close"})
        validators_b = requests.get(f"http://{stay_peer_0_1}/committee+val+keys/{min_id_b_0_1}", headers={"Connection":"close"})
        self.assertEqual(len(validators_a.json()), 8) # 8 in quorum 0
        self.assertEqual(len(validators_b.json()), 8) # 8 in quorum 1

        # Check how many API neighbors 0 and 1 have, should be 8 after a 0-2 peer leaves and is replaced by a 0-1 peer
        quorum_info = requests.get(f"http://{stay_peer_0_1}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a_0_1]), 8) # 8 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b_0_1]), 8) # 8 in quorum 1

        # Check how many sawtooth validators 0 and 2 have, should be 8 after a 0-2 peer leaves and is replaced by a 0-1 peer
        validators_a = requests.get(f"http://{replacement_peer_0_1}/committee+val+keys/{min_id_a_0_2}", headers={"Connection":"close"}).json()
        validators_b = requests.get(f"http://{replacement_peer_0_1}/committee+val+keys/{min_id_b_0_2}", headers={"Connection":"close"}).json()
        self.assertEqual(len(validators_a), 8) # 8 in quorum 0
        self.assertEqual(len(validators_b), 8) # 8 in quorum 2

        # Check how many API neighbors 0 and 2 have, should be 8 after a 0-2 peer leaves and is replaced by a 0-1 peer
        quorum_info = requests.get(f"http://{replacement_peer_0_1}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(len(quorum_info[min_id_a_0_2]), 8) # 8 in quorum 0
        self.assertEqual(len(quorum_info[min_id_b_0_2]), 8) # 8 in quorum 2
        
        # Make sure that the replacement joined the correct quorums, 0-1
        quorum_info = requests.get(f"http://{replacement_peer_0_1}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(list(quorum_info.keys()), min_quorums_0_2)
        
        # Make sure that the leaving peer is cleared out
        quorum_info = requests.get(f"http://{min_peer_0_2}/quorum+info", headers={"Connection":"close"}).json()
        self.assertEqual(list(quorum_info.keys()), [])

        

if __name__ == "__main__":
    unittest.main()
