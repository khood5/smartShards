import unittest
import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import run_command


def KILL_ALL_CONTAINERS():
    docker = dockerapi.from_env()
    for c in docker.containers.list():
        c.stop()
    docker.close()

# gets a list of all running container ids
def get_container_ids():
    docker = dockerapi.from_env()
    ids = []
    for c in docker.containers.list():
        ids.append(c.id)
    docker.close()
    return ids

class TestSawtoothMethods(unittest.TestCase):

    def test_start_container(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))

        # test that container is made empty
        sawtooth_instance = SawtoothContainer()
        assert (sawtooth_instance.id() is None)
        assert (sawtooth_instance.ip() is None)
        assert (sawtooth_instance.key() is None)

        # test that once an instance is started that it has an id, ip and key
        sawtooth_instance.start_instance()
        assert (len(docker.containers.list()) == 1)
        assert (sawtooth_instance.id() is not None)
        assert (sawtooth_instance.ip() is not None)
        assert (sawtooth_instance.key() is not None)

        container_ip = run_command(docker.containers.list()[0], "hostname -i")
        container_key = run_command(docker.containers.list()[0], "cat /etc/sawtooth/keys/validator.pub")
        assert (sawtooth_instance.id() == docker.containers.list()[0].id)
        assert (sawtooth_instance.ip() == container_ip)
        assert (sawtooth_instance.key() == container_key)
        number_of_running_processes = len(docker.containers.list()[0].top()['Processes'][0])
        # should only be 2 processes bash and tail -f /dev/null
        # each process has 4 columns so 2*4 = 8
        assert (number_of_running_processes == 8)

        # test that containers are made unique
        sawtooth_instance_2nd = SawtoothContainer()

        # test that container is made empty
        assert (sawtooth_instance_2nd.id() is None)
        assert (sawtooth_instance_2nd.ip() is None)
        assert (sawtooth_instance_2nd.key() is None)

        sawtooth_instance_2nd.start_instance()
        assert (len(docker.containers.list()) == 2)
        # tests that the two instance to not have the same IP or Key
        assert (sawtooth_instance.id() != sawtooth_instance_2nd.id())
        assert (sawtooth_instance.ip() != sawtooth_instance_2nd.ip())
        assert (sawtooth_instance.key() != sawtooth_instance_2nd.key())

        # clean up
        KILL_ALL_CONTAINERS()
        docker.close()

    def test_kill_container(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            self.skipTest("There should be no docker containers currently running, there was {} found.\n"
                          "Run \"docker ps\" to see all running containers".format(len(docker.containers.list())))
        sawtooth_instance = SawtoothContainer()
        sawtooth_instance.start_instance()
        assert (len(docker.containers.list()) == 1)
        assert (sawtooth_instance.id() in get_container_ids())

        sawtooth_instance_2nd = SawtoothContainer()
        sawtooth_instance_2nd.start_instance()
        assert (len(docker.containers.list()) == 2)
        assert (sawtooth_instance.id() in get_container_ids())
        assert (sawtooth_instance_2nd.id() in get_container_ids())

        # test that if one instance is stop only one instance stops
        sawtooth_instance.stop_instance()
        assert (len(docker.containers.list()) == 1)
        assert (sawtooth_instance_2nd.id() in get_container_ids())

        sawtooth_instance_2nd.stop_instance()
        assert (len(docker.containers.list()) == 0)

        # clean up
        KILL_ALL_CONTAINERS()
        docker.close()

    def test_committee_init_setup(self):
        print("test_committee_setup")

    def test_peer_join(self):
        print("test_join")

    def test_peer_leave(self):
        print("leave test")


if __name__ == '__main__':
    print("RUNNING {} TESTS".format(SawtoothContainer().__class__.__name__))
    unittest.main()
