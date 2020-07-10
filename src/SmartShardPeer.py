from src.api import create_app
import logging
import logging.handlers
import os

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

    def __init__(self, peer=None):
        self.port = DEFAULT_PORT
        self.api = create_app(peer)

    def start(self):
        if self.port is None:
            smart_shard_peer_log.error('start called with no PORT')
        self.api.run(port=self.port)
