import src.api as api
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.api.constants import PBFT_INSTANCES, QUORUMS, QUORUM_ID, TRANSACTION_KEY, TRANSACTION_VALUE, NEIGHBOURS, API_IP, ROUTE_EXECUTED_CORRECTLY
from src.api.constants import PORT, USER_KEY, VALIDATOR_KEY, DOCKER_IP
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.util import stop_all_containers
from src.api.api_util import get_plain_text
import docker as docker_api
import unittest
import json
import warnings
import time
import gc
from mock import patch, Mock
from requests import Response

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
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.300",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.400",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_B_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.500",  # ip for the API
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.600",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.700",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_A_JSON_MISSING_A_C = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.300",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            API_IP: "192.168.1.400",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

ADD_B_JSON_MISSING_B_D = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            API_IP: "192.168.1.500",  # ip for the API
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            API_IP: "192.168.1.700",
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
                PORT: "5000",
                QUORUM_ID: "c"
            },
            {
                API_IP: "192.168.1.300",
                PORT: "5000",
                QUORUM_ID: "d"
            },
            {
                API_IP: "192.168.1.400",
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
                API_IP: "192.168.1.200",
                PORT: "5000",
                QUORUM_ID: "c"
            },
            {
                API_IP: "192.168.1.300",
                PORT: "5000",
                QUORUM_ID: "d"
            },
            {
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

        peers[0].post('/submit/', json=TRANSACTION_A_JSON)
        time.sleep(3)

        for p in peers:
            self.assertEqual('999', get_plain_text(p.post('/get/', json=TRANSACTION_A_JSON)))
    
    @patch('requests.get')
    def test_min_intersection_all_equal_depth_0(self, mock_get):
        # Fully connected, 5 quorums
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {}, 'e': {}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {}}},
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {"192.168.1.600:5000": 0}, 'e': {}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {"192.168.1.200:5000": 0}, 'd': {}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.text = json.dumps(intersection_map)
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
        self.assertEqual(res.get_json(), ['a', 'b'])
    
    @patch('requests.get')
    def test_min_intersection_1_less_than_rest_depth_0(self, mock_get):
        # Almost fully connected, missing A-C peer
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {"192.168.1.600:5000": 0}, 'e': {}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {"192.168.1.600:5000": 0}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.text = json.dumps(intersection_map)
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
        self.assertEqual(res.get_json(), ['a', 'c'])
    
    @patch('requests.get')
    def test_min_intersection_2_less_than_rest_depth_0(self, mock_get):
        # Almost fully connected, missing A-C peer and B-D peer
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {}, 'e': {}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {"192.168.1.800:5000": 0}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {}}},
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {"192.168.1.900:5000": 0}}, 'd': {'e': {"192.168.1.1000:5000": 0}}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.text = json.dumps(intersection_map)
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
        self.assertEqual(res.get_json(), ['a', 'c'])
    
    @patch('requests.get')
    def test_min_intersection_all_equal_depth_1(self, mock_get):
        # Fully connected, 5 quorums
        intersection_maps = [
            {'a': {'b': {}, 'c': {"192.168.1.200:5000": 0}, 'd': {}, 'e': {}}, 'b': {'c': {}, 'd': {}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}},
            {'a': {'b': {}, 'c': {}, 'd': {"192.168.1.300:5000": 0}, 'e': {}}, 'b': {'c': {}, 'd': {}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}},
            {'a': {'b': {}, 'c': {}, 'd': {}, 'e': {"192.168.1.400:5000": 0}}, 'b': {'c': {}, 'd': {}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}},
            {'a': {'b': {}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {"192.168.1.500:5000": 0}, 'd': {}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}},
            {'a': {'b': {}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {}, 'd': {"192.168.1.600:5000": 0}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}},
            {'a': {'b': {}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {}, 'd': {}, 'e': {"192.168.1.700:5000": 0}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.text = json.dumps(intersection_map)
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
        res = test_client.get('/min+intersection/1')
        expected_intersection_map = {
            'a': {
                'b': {"localhost": 0}, 
                'c': {"192.168.1.200:5000": 0}, 
                'd': {"192.168.1.300:5000": 0}, 
                'e': {"192.168.1.400:5000": 0}}, 
            'b': {
                'c': {"192.168.1.500:5000": 0}, 
                'd': {"192.168.1.600:5000": 0}, 
                'e': {"192.168.1.700:5000": 0}}, 
            'c': {
                'd': {}, 
                'e': {}}, 
            'd': {
                'e': {}}
        }
        self.assertEqual(res.get_json(), expected_intersection_map)
    
    @patch('requests.get')
    def test_min_intersection_all_equal_depth_2(self, mock_get):
        # Fully connected, 5 quorums
        intersection_maps = [
            {'a': {'b': {"localhost": 0}, 'c': {}, 'd': {}, 'e': {}}, 'b': {'c': {}, 'd': {}, 'e': {}}, 'c': {'d': {}, 'e': {}}, 'd': {'e': {}}}
        ]
        side_effects = []
        for intersection_map in intersection_maps:
            res = Mock(spec=Response)
            res.text = json.dumps(intersection_map)
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
        res = test_client.get('/min+intersection/2')
        expected_intersection_map = {
            'a': {
                'b': {"localhost": 0}, 
                'c': {}, 
                'd': {}, 
                'e': {}}, 
            'b': {
                'c': {}, 
                'd': {}, 
                'e': {}}, 
            'c': {
                'd': {}, 
                'e': {}}, 
            'd': {
                'e': {}}
        }
        self.assertEqual(res.get_json(), expected_intersection_map)
    
    @patch('requests.post')
    def test_request_join(self, mock_post):
        side_effects = [
            ['a', 'b'],
            ROUTE_EXECUTED_CORRECTLY,
            ROUTE_EXECUTED_CORRECTLY
        ]
        mock_post.side_effect = side_effects
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        test_client = app.test_client()
        time.sleep(1)
        res = test_client.post('/request+join', json={API_IP: "192.168.0.0", PORT: 5000})


if __name__ == "__main__":
    unittest.main()
