import docker as dockerapi
from src.SawtoothPBFT import SawtoothContainer


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
