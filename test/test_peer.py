from src.Peer import Peer
from src.SawtoothPBFT import SawtoothContainer
from src.structures import Transaction
import time

def make_peer_committees(size: int):
    containers_A = [SawtoothContainer() for _ in range(size)]
    user_keys_A = [i.user_key() for i in containers_A]
    val_keys_A = [i.user_key() for i in containers_A]
    committee_ips_A = [i.ip() for i in containers_A]

    containers_B = [SawtoothContainer() for _ in range(size)]
    user_keys_B = [i.user_key() for i in containers_B]
    val_keys_B = [i.user_key() for i in containers_B]
    committee_ips_B = [i.ip() for i in containers_B]

    Aid = 1
    Bid = 2

    peers = [Peer(containers_A[i], containers_B[i], Aid, Bid) for i in range(size)]

    peers[0].make_genesis(Aid, val_keys_A, user_keys_A)
    peers[0].make_genesis(Bid, val_keys_B, user_keys_B)

    for p in peers:
        p.start_sawtooth(Aid, committee_ips_A, committee_ips_B)

    return peers

def test_transaction_confirmation():
    peers = make_peer_committees(4)
    Aid = 1
    Bid = 2
    tx_A = Transaction(Aid,1)
    tx_B = Transaction(Bid,1)
    for p in peers:
        p.submit(tx_A)
        p.submit(tx_B)
        tx_A.tx_number += 1
        tx_B.tx_number += 1
        time.sleep(3)  # make sure TX has time to be confirmed
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

def test_peer_join(self):
    peers = make_peer_committees(4)
    Aid = 1
    Bid = 2
    peers.append(Peer(SawtoothContainer(), SawtoothContainer(), Aid, Bid))
    committee_ips_A = [p.instance_a.ip() for p in peers]
    committee_ips_B = [p.instance_b.ip() for p in peers]
    
    peers[-1].peer_join(Aid, committee_ips_A)
    peers[0].update_committee(Aid, [p.instance_a.val_key() for p in peers], [p.instance_a.user_key() for p in peers])

    peers[-1].peer_join(Bid, committee_ips_B)
    peers[0].update_committee(Bid, [p.instance_b.val_key() for p in peers], [p.instance_b.user_key() for p in peers])

    tx_A = Transaction(Aid,3) # genesis+2 tx added 1 for membership and 1 for admin rights of new peer so length is 3
    tx_B = Transaction(Bid,3)

    # makes sure all peers are configured to work with each other (this is not a test of connectivity just config)
    # and make sure they all have the three tx
    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

        peers_config = p.instance_a.sawtooth_api('http://localhost:8008/peers')['data']
        for ip in committee_ips_A:
            if ip != p.ip():  # the peer it's self is not reported in the list
                self.assertIn("tcp://{}:8800".format(ip), peers_config)

        peers_config = p.instance_b.sawtooth_api('http://localhost:8008/peers')['data']
        for ip in committee_ips_B:
            if ip != p.ip():  # the peer it's self is not reported in the list
                self.assertIn("tcp://{}:8800".format(ip), peers_config)

    # check consensus still works
    peers[-1].submit(tx_A)
    peers[-1].submit(tx_B)
    tx_A.tx_number += 1
    tx_B.tx_number += 1
    time.sleep(3)
    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

def test_peer_leave(self):
    peers = make_peer_committees(7)
    Aid = 1
    Bid = 2
    old_peer = peers.pop()
    peers[0].update_committee(Aid, [p.instance_a.val_key() for p in peers], [p.instance_a.user_key() for p in peers])

    peers[0].update_committee(Bid, [p.instance_b.val_key() for p in peers], [p.instance_b.user_key() for p in peers])

    tx_A = Transaction(Aid,3) # genesis+2 tx added 1 for membership and 1 for admin rights of new peer so length is 3
    tx_B = Transaction(Bid,3)

    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

    del old_peer

    # check consensus still works
    peers[-1].submit(tx_A)
    peers[-1].submit(tx_B)
    tx_A.tx_number += 1
    tx_B.tx_number += 1
    time.sleep(3)
    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

    # remove multiple members
    old_peers = peers[:2]
    peers.pop()
    peers.pop()

    peers[0].update_committee(Aid, [p.instance_a.val_key() for p in peers], [p.instance_a.user_key() for p in peers])

    peers[0].update_committee(Bid, [p.instance_b.val_key() for p in peers], [p.instance_b.user_key() for p in peers])

    tx_A.tx_number += 2
    tx_B.tx_number += 2

    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)

    del old_peers

    # check consensus still works
    peers[-1].submit(tx_A)
    peers[-1].submit(tx_B)
    tx_A.tx_number += 1
    tx_B.tx_number += 1
    time.sleep(3)
    for p in peers:
        p.check_confirmation(tx_A)
        p.check_confirmation(tx_B)