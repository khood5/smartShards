from src.SawtoothPBFT import SawtoothContainer
from src.structures import Quorum
import time
import logging
import logging.handlers

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
sawtooth_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def peer_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    sawtooth_logger.propagate = console_logging
    sawtooth_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    sawtooth_logger.addHandler(handler)


class Peer:

    def __init__(self):
        self.instance_a = SawtoothContainer()
        self.instance_b = SawtoothContainer()
        self.tx_queue = []
        self.last_submit = 0
        self.a_id = None
        self.b_id = None

    def start_in(self, quorum_a: Quorum, quorum_b: Quorum):
        self.a_id = quorum_a.quorum_id()
        self.b_id = quorum_b.quorum_id()
        self.instance_a.join_sawtooth(quorum_a.members())
        self.instance_b.join_sawtooth(quorum_b.members())

    def submit_to_a(self, value: str, key: str):
        pass

    def submit_to_b(self, value: str, key: str):
        pass

    def __submit(self, value: str, key: str, quorum_id: int):
        if self.last_submit - time.time() > 3:

            self.last_submit = time.time()
