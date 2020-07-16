from src.api import create_app
from src.api.constants import PBFT_INSTANCES
import logging
import logging.handlers
import os
import multiprocessing as mp

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
smart_shard_peer_log = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def smart_shard_peer_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    smart_shard_peer_log.propagate = console_logging
    smart_shard_peer_log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    smart_shard_peer_log.addHandler(handler)


DEFAULT_PORT = 5000


class SmartShardPeer:

    def __init__(self, peer=None, port=DEFAULT_PORT):
        print("initializing SSP")
        self.port = port
        self.api = create_app(peer)
        self.app = None
        self.queue = mp.Queue()

    def __del__(self):
        print("deleting SSP")
        if self.app is not None:
            self.app.terminate()
            smart_shard_peer_log.info('terminating API on {}'.format(self.port))

    def add_to_queue(self, **ob):
        self.queue.put(ob)
        self.api.run()


    def start(self):
        print("starting SSP")
        if self.port is None:
            smart_shard_peer_log.error('start called with no PORT')
        if self.app is not None:
            smart_shard_peer_log.error('app on {} is already running'.format(self.port))
        print('a')
        #self.app = mp.Process(target=self.api.run, kwargs=({'port': self.port}))
        self.app = mp.Process(target=self.add_to_queue, kwargs=({'port': self.port}))
        self.app.daemon = True
        self.app.start()
        #print(q.get())
        #p.join()

    def pid(self):
        return self.app.pid

    def committee_id_a(self):
        return self.api.config[PBFT_INSTANCES].Aid

    def committee_id_b(self):
        return self.api.config[PBFT_INSTANCES].Bid
