import unittest


class TestSawtoothMethods(unittest.TestCase):

    def test_start_container(self):
        print("test_start")

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
    unittest.main()
