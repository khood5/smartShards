import os
import logging
import logging.handlers

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
intersection_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def intersection_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    intersection_logger.propagate = console_logging
    intersection_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    intersection_logger.addHandler(handler)


class Intersection:

    def __init__(self, sawtooth_container_a, sawtooth_container_b, Aid, Bid):
        self.instance_a = sawtooth_container_a
        self.instance_b = sawtooth_container_b
        self.committee_id_a = str(Aid) if Aid is not None else None
        self.committee_id_b = str(Bid) if Bid is not None else None

    def __del__(self):
        del self.instance_a
        del self.instance_b
    
    def get_instance(self, quorum_id):
        if str(quorum_id) == self.committee_id_a:
            return self.instance_a
        elif str(quorum_id) == self.committee_id_b:
            return self.instance_b
        else:
            return None

    def make_genesis(self, committee_id, val_keys, user_keys):
        instance = self.get_instance(committee_id)
        if instance is not None:
            instance.make_genesis(val_keys, user_keys)
        else:
            intersection_logger.error('PEER: make_genesis for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=committee_id))

    def start_sawtooth(self, committee_a_ips, committee_b_ips):
        self.instance_a.join_sawtooth(committee_a_ips)
        self.instance_b.join_sawtooth(committee_b_ips)

    def submit(self, tx):
        instance = self.get_instance(tx.quorum_id)
        if instance is not None:
            instance.submit_tx(tx.key, tx.value)
        else:
            intersection_logger.error('PEER: tx submitted for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=tx.quorum_id))

    def get_tx(self, tx):
        instance = self.get_instance(tx.quorum_id)
        if instance is not None:
            return instance.get_tx(tx.key)
        else:
            intersection_logger.error('PEER: tx submitted for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=tx.quorum_id))
        return None

    def ip(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.ip()
        else:
            intersection_logger.error('PEER: ip request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))

    def user_key(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.user_key()
        else:
            intersection_logger.error('PEER: user key request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None

    def val_key(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.val_key()
        else:
            intersection_logger.error('PEER: validator key request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None

    def blocks(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.blocks()['data']
        else:
            intersection_logger.error('PEER: blocks request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None

    def sawtooth_api(self, quorum_id, request):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.sawtooth_api(request)
        else:
            intersection_logger.error('PEER: sawtooth api request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None

    def peer_join(self, committee_id, committee_ips):
        instance = self.get_instance(committee_id)
        if instance is not None:
            instance.join_sawtooth(committee_ips)
        else:
            intersection_logger.error('PEER: peer tried to start in {q}, but peer is not in {q}. Peer in {a}, {b}'
                                      .format(q=committee_id, a=self.committee_id_a, b=self.committee_id_b))

    def update_committee(self, committee_id, val_keys):
        # Needed after a peer is deleted and when a peer joins
        instance = self.get_instance(committee_id)
        if instance is not None:
            return instance.update_committee(val_keys)

    def in_committee(self, committee_id):
        if str(committee_id) == self.committee_id_a or str(committee_id) == self.committee_id_b:
            return True
        return False

    def attached_network(self):
        if self.instance_a.attached_network() != self.instance_b.attached_network():
            intersection_logger.warning('PEER: containers attached to different networks, only a is given')
        return self.instance_a.attached_network()

    def get_committee_val_keys(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.get_committee_val_keys()
        else:
            intersection_logger.error('PEER: get peers request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None

    def get_committee_ips(self, quorum_id):
        instance = self.get_instance(quorum_id)
        if instance is not None:
            return instance.get_committee_ips()
        else:
            intersection_logger.error('PEER: get ips request for unknown quorum, '
                                      'known quorums:{known} requested quorum:{unknown}'.format(
                                        known=[self.committee_id_a, self.committee_id_b],
                                        unknown=quorum_id))
        return None