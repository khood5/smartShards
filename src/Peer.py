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

    def __init__(self, sawtooth_container_a, sawtooth_container_b, Aid, Bid):
        self.__instance_a = sawtooth_container_a
        self.__instance_b = sawtooth_container_b
        self.committee_id_a = Aid
        self.committee_id_b = Bid
        self.neighbors = []

    def __del__(self):
        del self.__instance_a
        del self.__instance_b

    def add_neighbor(self, neighbor_ip):
        if neighbor_ip not in self.neighbors:
            self.neighbors.append(neighbor_ip)

    def make_genesis(self, committee_id, val_keys, user_keys):
        if committee_id == self.committee_id_a:
            self.__instance_a.make_genesis(val_keys, user_keys)
        else:
            self.__instance_b.make_genesis(val_keys, user_keys)

    def start_sawtooth(self, committee_A_ips, committee_B_ips):
        self.__instance_a.start_sawtooth(committee_A_ips)
        self.__instance_b.start_sawtooth(committee_B_ips)

    def submit(self, tx):
        if tx.quorum_id == self.committee_id_a:
            self.__instance_a.submit_tx(tx.key, tx.value)

        elif tx.quorum_id == self.committee_id_b:
            self.__instance_b.submit_tx(tx.key, tx.value)
        else:
            peer_logger.error('PEER: tx submitted for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=tx.quorum_id))

    def get_tx(self, tx):
        if tx.quorum_id == self.committee_id_a:
            return self.__instance_a.get_tx(tx.key)

        elif tx.quorum_id == self.committee_id_b:
            return self.__instance_b.get_tx(tx.key)
        else:
            peer_logger.error('PEER: tx submitted for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=tx.quorum_id))
        return None

    def ip(self, quorum_id):
        if quorum_id == self.committee_id_a:
            return self.__instance_a.ip()
        elif quorum_id == self.committee_id_b:
            return self.__instance_b.ip()
        else:
            peer_logger.error('PEER: ip request for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=quorum_id))

    def user_key(self, quorum_id):
        if quorum_id == self.committee_id_a:
            return self.__instance_a.user_key()
        elif quorum_id == self.committee_id_b:
            return self.__instance_b.user_key()
        else:
            peer_logger.error('PEER: user key request for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=quorum_id))
        return None

    def val_key(self, quorum_id):
        if quorum_id == self.committee_id_a:
            return self.__instance_a.val_key()
        elif quorum_id == self.committee_id_b:
            return self.__instance_b.val_key()
        else:
            peer_logger.error('PEER: validator key request for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=quorum_id))
        return None

    def blocks(self, quorum_id):
        if quorum_id == self.committee_id_a:
            return self.__instance_a.blocks()['data']
        elif quorum_id == self.committee_id_b:
            return self.__instance_b.blocks()['data']
        else:
            peer_logger.error('PEER: blocks request for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=quorum_id))
        return None

    def sawtooth_api(self, quorum_id, request):
        if quorum_id == self.committee_id_a:
            return self.__instance_a.sawtooth_api(request)
        elif quorum_id == self.committee_id_b:
            return self.__instance_b.sawtooth_api(request)
        else:
            peer_logger.error('PEER: sawtooth api request for unknown quorum, '
                              'known quorums:{known} requested quorum:{unknown}'.format(known=[self.committee_id_a,
                                                                                               self.committee_id_b],
                                                                                        unknown=quorum_id))
        return None

    def peer_join(self, committee_id, committee_ips):
        if committee_id == self.committee_id_a:
            self.__instance_a.join_sawtooth(committee_ips)
        else:
            self.__instance_b.join_sawtooth(committee_ips)

    def update_committee(self, committee_id, val_keys, user_keys):
        # Needed after a peer is deleted and when a peer joins
        if committee_id == self.committee_id_a:
            self.__instance_a.update_committee(val_keys, user_keys)
        else:
            self.__instance_b.update_committee(val_keys, user_keys)
