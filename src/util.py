import docker as docker_api
from src.api.constants import API_IP, PORT, QUORUM_ID, PBFT_INSTANCES, NEIGHBOURS, QUORUMS, PENDING_PEERS, TCP_IP, USER_KEY, VALIDATOR_KEY, NETWORK_SIZE, ACCEPTED_PEERS, PENDING_PEERS, API_PORT
from src.SawtoothPBFT import SawtoothContainer
from src.SawtoothPBFT import DEFAULT_DOCKER_NETWORK
from src.Intersection import Intersection
from src.api.routes import ROUTE_EXECUTED_CORRECTLY, ROUTE_EXECUTION_FAILED
import os
import logging
import logging.handlers
import requests
import socket
import json
import time
from contextlib import closing

UPDATE_CONFIRMATION = 60

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
util_logger = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB
URL_REQUEST = "http://{hostname}:{port}/"


def util_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    util_logger.propagate = console_logging
    util_logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    util_logger.addHandler(handler)


def stop_all_containers():
    client = docker_api.from_env()
    for c in client.containers.list():
        c.stop(timeout=0)
    client.close()


# gets a list of all running container ids
def get_container_ids():
    client = docker_api.from_env()
    ids = []
    for c in client.containers.list():
        ids.append(c.id)
    client.close()
    return ids


def check_for_confirmation(peers, number_of_tx, tx_key="NO_KEY_GIVEN", timeout=UPDATE_CONFIRMATION):
    done = False
    start = time.time()
    while not done:
        time.sleep(0.5)
        done = True

        for p in peers:
            peers_blockchain = len(p.blocks()['data'])
            if number_of_tx > peers_blockchain:
                done = False
                break
        if time.time() - start > timeout:
            for p in peers:
                peers_blockchain = len(p.blocks()['data'])
                result = p.get_tx(tx_key)
                logging.critical("{ip}: TIMEOUT unable to confirm tx {key}:{r}".format(ip=p.ip(), key=tx_key,
                                                                                       r=result))
                logging.critical("{ip}: TIMEOUT blockchain length:{l} waiting for {nt}".format(ip=p.ip(),
                                                                                               l=peers_blockchain,
                                                                                               nt=number_of_tx))
            return False
    return True


# makes a test committee of user defined size
def make_sawtooth_committee(size: int, network=DEFAULT_DOCKER_NETWORK):
    if size < 4:
        logging.error("COMMITTEE IMPOSSIBLE: can not make committees of less then 4 members, {} asked for".format(size))
        return []
    if size < 7:
        logging.warning("COMMITTEE UNSTABLE: making committees of less then 7 members can lead to issues with adding "
                        "and removing. ")

    peers = [SawtoothContainer(network) for _ in range(size)]
    peers[0].make_genesis([p.val_key() for p in peers], [p.user_key() for p in peers])

    committee_ips = [p.ip() for p in peers]
    
    for p in peers:
        p.join_sawtooth(committee_ips)

    # if the there are a lot of containers running wait longer for process to start
    time.sleep(5 * size)

    done = False
    while not done:
        done = True
        for p in peers:
            if len(p.blocks()['data']) < 1:
                logging.info("Peer {ip} could not get genesis block\n"
                             "     blocks:{b}".format(ip=p.ip(), b=p.blocks()['data']))
                done = False
                time.sleep(0.5)
                break

    return peers


def make_single_intersection(instances: list, committee_size: int):
    peers = []
    for row in range(committee_size + 1):
        for column in range(row, committee_size):
            peers.append(Intersection(instances[row][column], instances[column + 1][row], row, column + 1), )
            util_logger.info("In committee {a} committee Member {a_ip} matches {b_ip} in committee {b}".format(
                a=row,
                a_ip=instances[row][column].ip(),
                b_ip=instances[column + 1][row].ip(),
                b=column + 1))

    return peers

def make_intersecting_committees(number_of_committees: int, intersections: int):
    pbft_instance = []
    committee_size = (number_of_committees - 1) * intersections
    for _ in range(number_of_committees):
        pbft_instance.append(make_sawtooth_committee(committee_size))

    peers = []
    # for committees with more then one intersection they are made by combining a series
    # of single intersecting committees, each entry in the series is a section
    for intersection in range(intersections):
        section_size = int(committee_size / intersections)
        start_of_section = section_size * intersection
        end_of_section = start_of_section + section_size + 1  # one past last element
        committee_section = [c[start_of_section:end_of_section] for c in pbft_instance]
        intersecting_peers = make_single_intersection(committee_section, section_size)
        peers += intersecting_peers
    return peers

def join_live_network(reference_peer):
    print("JLN RUNNING")
    from src.SmartShardPeer import SmartShardPeer

    reference_peer.refresh_config(QUORUMS, reference_peer.port)
    port_number = find_free_port()
    print("JLN GENERATED PORT " + str(port_number))
    #a = SawtoothContainer()
    #b = SawtoothContainer()
    #inter = Intersection(a, b, 'a', 'b')
    new_peer = SmartShardPeer(inter=None, port=port_number)
    new_peer.start()
    port_json = json.loads(json.dumps({
            PORT: new_peer.port
    }))
    url = "http://localhost:{port}/join_queue/".format(port=reference_peer.port)
    requests.post(url, json=port_json)

    reference_peer.notify_neighbors_pending_peer(new_peer.port)

    return new_peer


def get_neighbors(quorum, network: map):
    neighbors = []
    for neighbor_peer_port in network:
        neighbor_membership = [network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].committee_id_a,
                               network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].committee_id_b]

        if quorum == neighbor_membership[0]:
            neighbors.append({
                API_IP: "localhost",
                TCP_IP: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].ip(quorum),
                PORT: "{}".format(neighbor_peer_port),
                QUORUM_ID: "{}".format(neighbor_membership[1]),
                USER_KEY: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].user_key(neighbor_membership[1]),
                VALIDATOR_KEY: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].val_key(neighbor_membership[1])
            })

        if quorum == neighbor_membership[1]:
            neighbors.append({
                API_IP: "localhost",
                TCP_IP: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].ip(quorum),
                PORT: "{}".format(neighbor_peer_port),
                QUORUM_ID: "{}".format(neighbor_membership[0]),
                USER_KEY: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].user_key(neighbor_membership[0]),
                VALIDATOR_KEY: network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].val_key(neighbor_membership[0])
            })

    return neighbors

def refresh_config(type=None, config=None):
    print("running refresh_config type " + type + " with config ")
    print(config)
    if config[type] is not None:
        print("found the type")
        res_json = json.dumps({
            type: config[type]
        })
        print("refresh returning " + str(config[type]))
        print(res_json)
        return res_json
    else:
        print("refresh execution failed")
        return ROUTE_EXECUTION_FAILED

def check_pending_assigned(config, check_quorum=None, new_quorum=None, port=None, self_a=None, self_b=None):
    if check_quorum == new_quorum:
        return False, config
    if (config[PBFT_INSTANCES].committee_id_a == new_quorum and config[PBFT_INSTANCES].committee_id_b == check_quorum) or (config[PBFT_INSTANCES].committee_id_a == check_quorum and config[PBFT_INSTANCES].committee_id_b == new_quorum):
        return True, config

    quorums = config[QUORUMS]
    #self.refresh_config(PENDING_PEERS, self.port)

    for committee_id in quorums:
        for neighbor in quorums[committee_id]:
            neighbor_ip = neighbor[API_IP]
            neighbor_port = neighbor[PORT]

            url = "http://{address}:{port}/check_pending_endpoint/{check_quorum}/{new_quorum}".format(address=neighbor_ip, port=neighbor_port, new_quorum=new_quorum, check_quorum=check_quorum)
            pending_remotely = json.loads(requests.post(url, json={}).text)["assigned"]
            accepted_locally = False
                
            print("current accepted peers:")
            print(config[ACCEPTED_PEERS])

            accepted_remotely = False
            accepted_list = None

            try: 
                accepted_list = config[ACCEPTED_PEERS][new_quorum]
                print("1 step CPA")
            except KeyError:
                try:
                    config[ACCEPTED_PEERS][new_quorum] = {}
                    print("2 step CPA")
                except KeyError:
                    return ROUTE_EXECUTION_FAILED, config

            
            accepted_list = config[ACCEPTED_PEERS][new_quorum]

            try:
                if len(accepted_list[new_quorum][check_quorum]) > 0:
                    accepted_remotely = True
                    print("this quorum combination was already solved by")
                    print(accepted_list[new_quorum][check_quorum])
            except KeyError:
                for accepted_quorum in accepted_list: 
                    if (config[PBFT_INSTANCES].committee_id_a == accepted_quorum and config[PBFT_INSTANCES].committee_id_b == new_quorum) or (config[PBFT_INSTANCES].committee_id_a == new_quorum and config[PBFT_INSTANCES].committee_id_b == accepted_quorum):
                        print(str(new_quorum) + " , " + str(accepted_quorum) + " already active on us")
                        continue
                    else:
                        print(str(new_quorum) + " , " + str(accepted_quorum) + " not active on us. Our committees are ")
                        print([config[PBFT_INSTANCES].committee_id_a, config[PBFT_INSTANCES].committee_id_b])
                        print("we were checking for ")
                        print([accepted_quorum, new_quorum])
                    for accepted_port in accepted_list[accepted_quorum]:
                        print("accepted port: " + str(accepted_port))
                        if (accepted_list[accepted_quorum][accepted_port] == True):
                            print(str(accepted_port) + " was found ")
                            accepted_remotely = True
                            config = activate_new_quorum(config, str(accepted_port), accepted_quorum, new_quorum, self_a, self_b, False)

            try:
                accepted_locally = accepted_list[port]
            except:
                pass

            print("found pending_remotely " + str(pending_remotely))
            print("found accepted_locally " + str(accepted_locally))
            print("found accepted_remotely " + str(accepted_remotely))
            if pending_remotely == True or accepted_locally == True or accepted_remotely == True:
                print("IN CPAROUTE RETURN TRUE")
                return True, config
    print("IN CPAROUTE RETURN FALSE")
    return False, config

def get_pending_quorum(config, joining_port):
    pending_quorum = None

    # No peers are currently awaiting enough nodes to start
    if len(config[PENDING_PEERS]) == 0:
        highest_quorum_num = 0
        highest_quorum_id = None

        for quorum in config[QUORUMS]:
            our_quorum_num = int(quorum)
            if our_quorum_num > highest_quorum_num:
                highest_quorum_num = our_quorum_num
                highest_quorum_id = quorum

            neighbors = config[QUORUMS][quorum]
            for neighbor in neighbors:
                found_quorum_id = neighbor[QUORUM_ID]
                found_quorum_num = int(found_quorum_id)
                if found_quorum_num > highest_quorum_num:
                    highest_quorum_num = found_quorum_num
                    highest_quorum_id = found_quorum_id

        id_a = config[PBFT_INSTANCES].committee_id_a
        id_b = config[PBFT_INSTANCES].committee_id_b

        highest_local_quorum = max(int(id_a), int(id_b))

        if highest_local_quorum > highest_quorum_num:
            highest_quorum_num = highest_local_quorum
            highest_quorum_id = chr(highest_quorum_num + 48)

        next_quorum_num = highest_quorum_num + 1  
        next_quorum_id = chr(next_quorum_num + 48)
        pending_quorum = next_quorum_id

        config[PENDING_PEERS][pending_quorum] = []
        config[NETWORK_SIZE] = next_quorum_num
    else: # A peer is awaiting new nodes: assign new node to the top peer
        pending = config[PENDING_PEERS]
        pending_quorum = list(pending.keys())[0]

    try:
        check = config[PENDING_PEERS][pending_quorum].index(joining_port)
        return False, config # The node has already been queued
    except ValueError:
        pass 
    except AttributeError:
        del config[PENDING_PEERS][pending_quorum]
        return -1, config


    return pending_quorum, config

def activate_new_quorum(config, port, str_index, str_pending, self_a, self_b, genesis):
    print("[" + str(config[API_PORT]) + "] Peer on port " + port + " will be member of quorums " + str_index + ", " + str_pending)

    neighbors = {}

    quorum_add = str_index
    next_quorum = str_pending

    for quorum in config[QUORUMS]:
        self_added = False
        for neighbor in config[QUORUMS][quorum]:
            url = "http://localhost:{remote_port}/new_live_peer/{new_port}/{check_quorum}/{new_quorum}".format(remote_port=neighbor[PORT], new_port=port, check_quorum=str_index, new_quorum=str_pending)
            requests.post(url, json={})

            if quorum == neighbor[QUORUM_ID]:
                continue

            try:
                neighbors[quorum_add].append(neighbor)
            except KeyError:
                neighbors[quorum_add] = []
                
                if not self_added:
                    if self_a[QUORUM_ID] != str_index:
                        neighbors[quorum_add].append(self_a)
                    if self_b[QUORUM_ID] != str_index:
                        neighbors[quorum_add].append(self_b)
                    self_added = True
                    try:
                        config[ACCEPTED_PEERS][str_pending][str_index][port] = True
                    except KeyError:
                        try:
                            config[ACCEPTED_PEERS][str_pending][str_index] = {}
                        except KeyError:
                            try:
                                config[ACCEPTED_PEERS][str_pending] = {}
                            except KeyError as e:
                                print("Peer was unable to activate new quorum")
                                print(e)
                                return ROUTE_EXECUTION_FAILED.format(msg="") + "Peer was unable to activate new quorum \n\n\n{}".format(e)
                    config[ACCEPTED_PEERS][str_pending][str_index][port] = True
                
                if neighbor[QUORUM_ID] != str_index:
                    neighbors[quorum_add].append(neighbor)

        quorum_add = next_quorum
    assert(len(config[QUORUMS]) == 2)

    print("Calculated neighbors for new intersection at (" + str_index + ", " + str_pending + ")\n")
    print(neighbors)

    start_json = json.loads(json.dumps({
        "id_a": str_index,
        "id_b": str_pending,
        "neighbors": neighbors,
        "genesis": genesis
    }))
    url = "http://localhost:{port}/spin_up_intersection/".format(port=port)
    requests.post(url, json=start_json)
    
    return config


def process_pending_quorums(config, pending_quorum, joining_port, self_a, self_b):

    try:
        t = config[PENDING_PEERS][pending_quorum]
    except KeyError:
        # Bad quorum requested
        return config

    config[PENDING_PEERS][pending_quorum].append(str(joining_port))

    print(config[PENDING_PEERS][pending_quorum]) 
    print(str(pending_quorum))

    if len(config[PENDING_PEERS][pending_quorum]) >= int(pending_quorum):
        for joining_peer in config[PENDING_PEERS][pending_quorum]:
            if joining_peer is None:
                print("found no JP")
                continue
            if config[PENDING_PEERS][pending_quorum] is None:
                print("JP was neutralized")
                continue
            
            index = None
            first_run = True
            accepted_locally = False

            str_joining = str(joining_peer)

            config[ACCEPTED_PEERS] = json.loads(refresh_config(ACCEPTED_PEERS, config))[ACCEPTED_PEERS]

            print("checking accepted peers")
            print(config[ACCEPTED_PEERS])

            pending_for_quorum = None

            try:
                pending_for_quorum = config[PENDING_PEERS][pending_quorum]
                print("no cfgerr")
            except KeyError as err:
                print("corrected config err")
                print(err)

                if first_run == True:
                    config[PENDING_PEERS][pending_quorum] = []
                    config[PENDING_PEERS][pending_quorum].append(joining_peer)
                    pending_for_quorum = config[PENDING_PEERS][pending_quorum]
                    first_run = False

            try: 
                index = config[PENDING_PEERS][pending_quorum].index(joining_peer)
            except ValueError as err:
                print(err)
                print("valueerror for index find")
                config[PENDING_PEERS][pending_quorum].append(joining_peer)
                index = config[PENDING_PEERS][pending_quorum].index(joining_peer)

            try:
                accepted_locally = config[ACCEPTED_PEERS][str(pending_quorum)][str(index)][str_joining]
                print("Found config[accepted_peers][" + str_joining + "] = " + str(config[ACCEPTED_PEERS][str(pending_quorum)][str_joining]))
            except KeyError as err:
                print("node not marked accepted yet")
                print(err)
                print(config[ACCEPTED_PEERS])

            print("after checks, cfg pendingpeers is")
            print(config[PENDING_PEERS])

            str_index = str(index)
            str_pending = str(pending_quorum)
    
            if str_index == str_pending:
                print("index and pending match, skipping")
                continue
            print("NET SIZE " + str(config[NETWORK_SIZE]) + " index " + str_index + " PQ " + str_pending)

            found, config = check_pending_assigned(config, str_index, str_pending, str_joining, self_a, self_b)
            
            if accepted_locally == True or found == True:
                print("WAS ALREADY FOUND - SKIPPING")
                continue

            config = activate_new_quorum(config, str_joining, str_index, str_pending, self_a, self_b, True)
            print("before attempt delete in activate")
            print(config[PENDING_PEERS])

            if str_joining in config[PENDING_PEERS][str_pending]:
                print("checking for port " + str_joining)
                print("pending check " + str(len(config[PENDING_PEERS][str_pending])) + " | " + str(config[NETWORK_SIZE]))

                if len(config[PENDING_PEERS][str_pending]) >= config[NETWORK_SIZE]:
                    
                    add = 1 + len(config[PENDING_PEERS][str_pending]) - int(str_pending)
                    config[NETWORK_SIZE] += add
                    print("size is now " + str(config[NETWORK_SIZE]) + ", increased by " + str(add))

                    config[PENDING_PEERS][str_pending].remove(str_joining)

                    #del config[PENDING_PEERS][str_pending]
            
            print("Set config[accepted_peers][" + str_pending + "][" + str_index + "][" + str_joining + "] = " + str(config[ACCEPTED_PEERS][str_pending][str_index][str_joining]))
            
    return config


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


# starts a set of peers on the same host (differentiated by port number)
# returns a dict {portNumber : SmartShardPeer}
def make_intersecting_committees_on_host(number_of_committees: int, intersections: int):
    inter = make_intersecting_committees(number_of_committees, intersections)
    peers = {}

    from src.SmartShardPeer import SmartShardPeer

    for i in inter:
        port_number = find_free_port()
        peers[port_number] = SmartShardPeer(i, port_number)
        peers[port_number].start()

    for port in peers:
        quorum_id = peers[port].app.api.config[PBFT_INSTANCES].committee_id_a
        other_peers = {}
        for p in peers:
            if peers[p].port != port:
                other_peers[p] = peers[p]
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        url = "http://localhost:{port}/add/{quorum}".format(port=port, quorum=quorum_id)
        requests.post(url, json=add_json)

        quorum_id = peers[port].app.api.config[PBFT_INSTANCES].committee_id_b
        add_json = json.loads(json.dumps({
            NEIGHBOURS: get_neighbors(quorum_id, other_peers)
        }))
        url = "http://localhost:{port}/add/{quorum}".format(port=port, quorum=quorum_id)
        requests.post(url, json=add_json)

        peers[port].refresh_config(QUORUMS, port)

    return peers
