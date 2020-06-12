import src.api as api
from src.api.constants import PEER, QUORUMS, QUORUM_ID, TRANSACTION_KEY, TRANSACTION_VALUE, NEIGHBOURS, IP_ADDRESS
from src.api.constants import PORT, USER_KEY, VALIDATOR_KEY
from src.SawtoothPBFT import VALIDATOR_KEY as VKEY
from src.SawtoothPBFT import USER_KEY as UKEY
from src.util import stop_all_containers
import docker as docker_api
import unittest
from mock import patch
import json
import warnings
import threading

TRANSACTION_A_JSON = json.loads(json.dumps({QUORUM_ID: "a",
                                            TRANSACTION_KEY: "test",
                                            TRANSACTION_VALUE: "999"}))

TRANSACTION_C_JSON = json.loads(json.dumps({QUORUM_ID: "c",
                                            TRANSACTION_KEY: "test",
                                            TRANSACTION_VALUE: "999"}))

JOIN_A_JSON = json.loads(json.dumps({
    NEIGHBOURS: [
        {
            IP_ADDRESS: "192.168.1.200",
            PORT: "5000",
            QUORUM_ID: "c"
        },
        {
            IP_ADDRESS: "192.168.1.300",
            PORT: "5000",
            QUORUM_ID: "d"
        },
        {
            IP_ADDRESS: "192.168.1.400",
            PORT: "5000",
            QUORUM_ID: "e"
        }
    ]
}))

MAKE_GENESIS_JSON = json.loads(json.dumps({
    USER_KEY: ["U_key1", "U_key2", "U_key3"],
    VALIDATOR_KEY: ["VAL_key1", "VAL_key2", "VAL_key3"]
}))


def get_plain_test(response):
    return response.data.decode("utf-8")


def start_test_peer(port=5000):
    app = api.create_app()
    app_thread = threading.Thread(target=app.run, kwargs={'port': port})
    app_thread.start()
    return app_thread


class TestAPI(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter('ignore', category=ResourceWarning)
        docker = docker_api.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        docker.close()

    def tearDown(self) -> None:
        stop_all_containers()

    def test_api_start(self):
        app = api.create_app()
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        client = app.test_client()

        # test that wrong url do nothing
        response = client.get('/start/')
        self.assertEqual(404, response.status_code)
        self.assertIsNone(app.config[PEER])
        self.assertEqual({}, app.config[QUORUMS])
        response = client.get('/start/a/')
        self.assertEqual(404, response.status_code)
        self.assertIsNone(app.config[PEER])
        self.assertEqual({}, app.config[QUORUMS])

        # test actual url works
        response = client.get('/start/a/b')
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(app.config[PEER])
        self.assertEqual({'a': [], 'b': []}, app.config[QUORUMS])
        docker = docker_api.from_env()
        self.assertEqual(2, len(docker.containers.list()))

        # get info on container a
        container_ip = docker.containers.list()[1].exec_run("hostname -i").output.decode('utf-8').strip()
        container_val_key = docker.containers.list()[1].exec_run("cat {val_pub}".format(val_pub=VKEY["pub"])) \
            .output.decode('utf-8').strip()
        container_user_key = docker.containers.list()[1].exec_run("cat {user_pub}".format(user_pub=UKEY["pub"])) \
            .output.decode('utf-8').strip()

        self.assertEqual(get_plain_test(client.get('/ip/a')), container_ip)
        self.assertEqual(get_plain_test(client.get('/val+key/a')), container_val_key)
        self.assertEqual(get_plain_test(client.get('/user+key/a')), container_user_key)
        self.assertNotEqual(get_plain_test(client.get('/val+key/a')), get_plain_test(client.get('/user+key/a')))

        # get info on container b
        container_ip = docker.containers.list()[0].exec_run("hostname -i").output.decode('utf-8').strip()
        container_val_key = docker.containers.list()[0].exec_run("cat {val_pub}".format(val_pub=VKEY["pub"])) \
            .output.decode('utf-8').strip()
        container_user_key = docker.containers.list()[0].exec_run("cat {user_pub}".format(user_pub=UKEY["pub"])) \
            .output.decode('utf-8').strip()

        self.assertEqual(get_plain_test(client.get('/ip/b')), container_ip)
        self.assertEqual(get_plain_test(client.get('/val+key/b')), container_val_key)
        self.assertEqual(get_plain_test(client.get('/user+key/b')), container_user_key)
        self.assertNotEqual(get_plain_test(client.get('/val+key/b')), get_plain_test(client.get('/user+key/b')))

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
                IP_ADDRESS: "192.168.1.200",
                PORT: "5000",
                QUORUM_ID: "c"
            },
            {
                IP_ADDRESS: "192.168.1.300",
                PORT: "5000",
                QUORUM_ID: "d"
            },
            {
                IP_ADDRESS: "192.168.1.400",
                PORT: "5000",
                QUORUM_ID: "e"
            }
        ], app.config[QUORUMS]["a"])

        self.assertEqual(app.config[QUORUMS]["b"], [])


if __name__ == "__main__":
    unittest.main()
