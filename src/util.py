import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer
from src.Peer import Peer


def stop_all_containers():
    client = dockerapi.from_env()
    for c in client.containers.list():
        c.stop(timeout=0)
    client.close()


# gets a list of all running container ids
def get_container_ids():
    client = dockerapi.from_env()
    ids = []
    for c in client.containers.list():
        ids.append(c.id)
    client.close()
    return ids


# makes a test committee of user defined size
def make_sawtooth_committee(size: int):
    peers = [SawtoothContainer() for _ in range(size)]
    peers[0].make_genesis([p.val_key() for p in peers], [p.user_key() for p in peers])
    committee_ips = [p.ip() for p in peers]
    for p in peers:
        p.join_sawtooth(committee_ips)

    done = False
    while not done:
        done = True
        for p in peers:
            if len(p.blocks()['data']) != 1:
                done = False

    return peers


# makes 2 quorums each with size number of peers (with whole committee intersection i.e. each peer is in both quorums)
def make_peer_committees(size: int, id_a=1, id_b=2):
    containers_a = make_sawtooth_committee(size)
    containers_b = make_sawtooth_committee(size)
    peers = [Peer(containers_a[i], containers_b[i], id_a, id_b) for i in range(size)]

    return peers
