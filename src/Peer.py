from src.SawtoothPBFT import SawtoothContainer
import os
import logging
import logging.handlers

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
peer_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def peer_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    peer_logger.propagate = console_logging
    peer_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    peer_logger.addHandler(handler)


class Peer:

    def __init__(self, sawtoothcontainer1, sawtoothcontainer2, Aid, Bid):
        self.instance_a = sawtoothcontainer1
        self.instance_b = sawtoothcontainer2
        self.a_id = Aid
        self.b_id = Bid

    def make_genesis(self, committee_id, val_keys, user_keys):
        if committee_id == self.a_id:
            self.instance_b.make_genesis(val_keys, user_keys)
        else:
            self.instance_b.make_genesis(val_keys, user_keys)

    def start_sawtooth(self, committee_A_ips, committee_B_ips):
        self.instance_a.start_sawtooth(committee_A_ips)
        self.instance_a.start_sawtooth(committee_B_ips)

    def submit(self, tx):
        if tx.quorumid == self.a_id:
            #self.instance_a.submit_tx(tx)
            self.instance_a.submit_tx('test{}'.format(tx.tx_number), '999')

        else:
            #self.instance_b.submit_tx(tx)
            self.instance_a.submit_tx('test{}'.format(tx.tx_number), '999')

    def check_confirmation(self, tx):
        if tx.quorumid == self.a_id:
            blockchain_size = len(self.instance_a.blocks()['data'])
            self.instance_a.assertEqual(tx.tx_number, blockchain_size)
        else:
            blockchain_size = len(self.instance_b.blocks()['data'])
            self.instance_b.assertEqual(tx.tx_number, blockchain_size)

    def peer_join(self, committee_id, committee_ips):
        if committee_id == self.a_id:
            self.instance_a.join_sawtooth(committee_ips)
        else:
            self.instance_b.join_sawtooth(committee_ips)

    def update_committee(self, committee_id, val_keys, user_keys):
        # Needed after a peer is deleted and when a peer joins
        if committee_id == self.a_id:
            self.instance_a.update_committee(val_keys, user_keys)
        else:
            self.instance_b.update_committee(val_keys, user_keys)
