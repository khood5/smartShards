import unittest
import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import run_command


class TestSawtoothMethods(unittest.TestCase):

    def test_start_container(self):
        docker = dockerapi.from_env()
        if len(docker.containers.list()) is not 0:
            raise Exception("There should be no docker containers currently running, there was {} found.\n"
                            "Run \"docker ps\" to see all running containers"
                            .format(len(docker.containers.list())))

        # test that container is made empty
        sawtooth_instance = SawtoothContainer()
        assert (sawtooth_instance.id() is None)
        assert (sawtooth_instance.ip() is None)
        assert (sawtooth_instance.key() is None)

        # test that once an instance is started that it has an id, ip and key
        sawtooth_instance.start_instance()
        assert (sawtooth_instance.id() is not None)
        assert (sawtooth_instance.ip() is not None)
        assert (sawtooth_instance.key() is not None)

        container_ip = run_command(docker.containers.list()[0], "hostname -i")
        container_key = run_command(docker.containers.list()[0], "cat /etc/sawtooth/keys/validator.pub")
        assert (sawtooth_instance.id() == docker.containers.list()[0].id)
        assert (sawtooth_instance.ip() == container_ip)
        assert (sawtooth_instance.key() == container_key)
        number_of_running_processes = len(docker.containers.list()[0].top()[0])
        assert (number_of_running_processes == 2)  # should only be two processes bash and tail -f /dev/null

        # test that containers are made unique
        sawtooth_instance_2nd = SawtoothContainer()

        # test that container is made empty
        assert (sawtooth_instance_2nd.id() is None)
        assert (sawtooth_instance_2nd.ip() is None)
        assert (sawtooth_instance_2nd.key() is None)

        # tests that the two instance to not have the same IP or Key
        assert (sawtooth_instance.id() != sawtooth_instance_2nd.id())
        assert (sawtooth_instance.ip() != sawtooth_instance_2nd.ip())
        assert (sawtooth_instance.key() != sawtooth_instance_2nd.key())

        


    def test_kill_container(self):
        print("test_kill")

    def test_ip_assignment(self):
        print("test_ip_assignment")

    def test_committee_init_setup(self):
        print("test_committee_setup")

    def test_peer_join(self):
        print("test_join")

    def test_peer_leave(self):
        print("leave test")


if __name__ == '__main__':
    print("RUNNING {} TESTS".format(SawtoothContainer().__class__.__name__))
    unittest.main()
