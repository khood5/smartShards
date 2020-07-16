from src.api import create_app
import logging
import logging.handlers
import os
from src.api.routes import shutdown
from flask import request
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
        self.port = port
        self.api = create_app(peer)
        self.peer = peer
        self.id = os.getpid()
        self.app = None

    def __del__(self):
        shutdown(self.id) # this does not actually stop the flask server. Seems to be impossible to do so.
        del self.id
        del self.port
        del self.peer
        if self.app is not None:
            self.app.terminate()
            smart_shard_peer_log.info('terminating API on {}'.format(self.port))

    def start(self):
        if self.port is None:
            smart_shard_peer_log.error('start called with no PORT')
        if self.app is not None:
            smart_shard_peer_log.error('app on {} is already running'.format(self.port))
        self.app = mp.Process(target=self.api.run, kwargs=({'port': self.port}))
        self.app.daemon = True  # run the api as daemon so it terminates with the peer process process
        self.app.start()

    def pid(self):
        return self.id
