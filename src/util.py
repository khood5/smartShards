import docker as docker_api
from src.api.constants import API_IP, PORT, QUORUM_ID, PBFT_INSTANCES, NEIGHBOURS, QUORUMS, PENDING_PEERS, TCP_IP, USER_KEY, VALIDATOR_KEY, NETWORK_SIZE, ACCEPTED_PEERS, PENDING_PEERS, API_PORT, FINALIZED_PEERS
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

    reference_peer.app.api.config = refresh_config_remote(reference_peer.app.api.config, QUORUMS, reference_peer.port)

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

    #reference_peer.app.api.config = notify_neighbors_pending_peer(reference_peer.app.api.config, new_peer.port)

    return new_peer, reference_peer.app.api.config


def get_neighbors(quorum, network: map):
    neighbors = []
    for neighbor_peer_port in network:
        neighbor_membership = None
        try:
            neighbor_membership = [network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].committee_id_a,
                                network[neighbor_peer_port].app.api.config[PBFT_INSTANCES].committee_id_b]
        except KeyError:
            print("huh " + str(network[neighbor_peer_port].app.api.config))

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

def get_cfg(type=None, config=None):
    if config[type] is not None:
        return config[type]
    else:
        return ROUTE_EXECUTION_FAILED

def refresh_config_remote(config, type, port):
    #print("CFG AT START - C  - " + str(config))
    url = "http://localhost:{port}/refresh_config/{type}".format(port=port, type=type)
    response = requests.post(url, json={})
    response_txt = response.text

    recv_cfg = json.loads(response_txt)
    config[type] = recv_cfg
    print("refreshed cfg type " + type)
    #print(recv_cfg)

    #print("CFG AT END - D  - " + str(config))
    return config

def notify_neighbors_pending_peer(config, pending_port=None, already_notified={}):
    try:
        check = already_notified[str(config[API_PORT])]
        print(str(config[API_PORT]) + " has already been notified, skipping FROM TOP")
        return config
    except KeyError:
        pass

    #print("CFG AT START - A  - " + str(config))
    str_port = str(config[API_PORT])
    config = refresh_config_remote(config, QUORUMS, str_port)
    config = refresh_config_remote(config, PENDING_PEERS, str_port)

    quorums = config[QUORUMS]

    print("[" + str_port + "] Pending peer joining: " + str(pending_port) + " -> " + str(config[PENDING_PEERS]))

    for committee_id in quorums:
        for neighbor in quorums[committee_id]:
            neighbor_port = neighbor[PORT]

            try:
                check = already_notified[neighbor_port]
                print(str(neighbor_port) + " has already been notified, skipping")
                continue
            except KeyError:
                pass

            neighbor_ip = neighbor[API_IP]

            url = "http://{address}:{port}/new_pending_peer/{pending_port}".format(pending_port=pending_port,
                                                                        address=neighbor_ip, port=neighbor_port)
            ignore_json = json.dumps({"already_notified": already_notified})
            notify_neighbor(url, ignore_json)

    #print("CFG AT END - B  - " + str(config))
    return config

def notify_neighbor(url, json={}):
    attempts = 0
    while attempts < 5:
        attempts += 1
        try:
            requests.post(url, json=json)
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            continue

        break

        if attempts > 5:
            return False

    return True

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
    #import traceback
    #traceback.print_stack()
    print("[" + str(config[API_PORT]) + "] Peer on port " + port + " will be member of quorums " + str_index + ", " + str_pending)

    neighbors = {}

    quorum_add = str_index
    next_quorum = str_pending

    for quorum in config[QUORUMS]:
        self_added = False
        for neighbor in config[QUORUMS][quorum]:

            # Notify each neighbor of the new live peer
            url = "http://localhost:{remote_port}/new_live_peer/{new_port}/{check_quorum}/{new_quorum}".format(remote_port=neighbor[PORT], new_port=port, check_quorum=str_index, new_quorum=str_pending)
            requests.post(url, json={})

            # Skip nodes who are in the same quorum as joining peer
            if quorum == neighbor[QUORUM_ID]:
                continue

            try:
                neighbors[quorum_add].append(neighbor)
            except KeyError:
                # This quorum's list has not been created yet; create it
                neighbors[quorum_add] = []
                
                # Only add neighbor information for the sending node once per quorum
                if not self_added:
                    # Don't add neighbor information for the sending node
                    if self_a[QUORUM_ID] != str_index:
                        neighbors[quorum_add].append(self_a)
                    if self_b[QUORUM_ID] != str_index:
                        neighbors[quorum_add].append(self_b)
                    self_added = True

                    # Add node to accepted list
                    try:
                        config[ACCEPTED_PEERS][str_pending][str_index][port] = True
                    except KeyError:
                        try:
                            config[ACCEPTED_PEERS][str_pending][str_index] = {}
                        except KeyError:
                            try:
                                config[ACCEPTED_PEERS][str_pending] = {}
                                config[ACCEPTED_PEERS][str_pending][str_index] = {}
                            except KeyError as e:
                                print("Peer was unable to activate new quorum")
                                print(e)
                                return ROUTE_EXECUTION_FAILED.format(msg="") + "Peer was unable to activate new quorum \n\n\n{}".format(e)
                    config[ACCEPTED_PEERS][str_pending][str_index][port] = True

                    # Remove accepted node from the pending list
                    try:
                        config[PENDING_PEERS][str_pending].remove(port)
                        print("removing from qu")
                    except ValueError:
                        print("not found in pending, remove skipped")
                        pass
                
                if neighbor[QUORUM_ID] != str_index:
                    neighbors[quorum_add].append(neighbor)

        quorum_add = next_quorum
    assert(len(config[QUORUMS]) == 2)

    print("Calculated new intersection at (" + str_index + ", " + str_pending + ")\n")

    config[FINALIZED_PEERS][port] = [str_index, str_pending]

    # There are enough accepted peers to spin up an intersection
    if len(config[ACCEPTED_PEERS][str_pending][str_index]) >= int(str_pending):
        config[NETWORK_SIZE] += 1

        start_json = json.loads(json.dumps({
            "id_a": str_index,
            "id_b": str_pending,
            "neighbors": neighbors,
            "genesis": genesis
        }))
        url = "http://localhost:{port}/spin_up_intersection/".format(port=port)
        requests.post(url, json=start_json)
    
    return config

def pending_quorum_loop(config, pending_pos, pending_quorum, offset, intersections_made, self_a, self_b):
    str_pending = str(pending_quorum)
    num_pending = int(pending_quorum)
    adj_pos = offset - pending_pos
    joining_peer = None
    
    try:
        joining_peer = config[PENDING_PEERS][pending_quorum][adj_pos]
    except IndexError as err:
        try:
            check = config[PENDING_PEERS][pending_quorum]
        except IndexError as err:
            config[PENDING_PEERS][pending_quorum] = {}
            #config[PENDING_PEERS][pending_quorum][adj_pos] = 
    pending_port = str(joining_peer)

    str_pos = str(adj_pos)
    str_raw_pos = str(pending_pos)

    print(str(config[API_PORT]) + " trying port: " + pending_port + "\t" + str_raw_pos + "\t" + str_pending + "\t(offset is " + str_pos + ")")

    # Out of range
    if adj_pos >= num_pending:
        print("NODE OUT OF RANGE, SKIPPING")
        offset -= (1 + (adj_pos - num_pending))
        return config, offset, intersections_made

    print("checking accepted peers")
    print(config[ACCEPTED_PEERS])

    if intersections_made < num_pending:
        try:
            all_accepted_quorums = config[ACCEPTED_PEERS][str_pending].copy()
            for quorum in all_accepted_quorums:
                check = []
                try:
                    check = config[FINALIZED_PEERS][str(pending_port)]
                    a = check[0]
                    b = check[1]

                except IndexError as e:
                    try:
                        if quorum == str_raw_pos:
                            print("QUORUM ALREADY ASSIGNED, SKIPPING")

                            correct_port = str(next(iter(all_accepted_quorums[quorum])))
                            intersections_made += 1
                            offset += 1

                            config = activate_new_quorum(config, correct_port, str_raw_pos, str_pending, self_a, self_b, False)
                            
                            return config, offset, intersections_made
                        port_in_different_quorum = all_accepted_quorums[quorum][pending_port]
                        if port_in_different_quorum:
                            print("NODE ACCEPTED IN ANOTHER QUORUM, SKIPPING")
                            offset += 1
                            return config, offset, intersections_made
                    except KeyError:
                        pass
                    
                if ((check[0] == quorum) and (check[1] == str_pending)):
                    print("MATCHED CASE")
                    offset += 1
                    return config, offset, intersections_made
                else:
                    print("match failed.")
                    print(config[FINALIZED_PEERS])
                    print(quorum)
                    print(str_pending)

        except KeyError:
            pass

        try:
            # Check if node has been assigned to this quorum aleady
            accepted_locally = config[ACCEPTED_PEERS][str_pending][str_raw_pos][pending_port]
            print("Found config[accepted_peers][" + str_pending + "][" + str_raw_pos + "][" + pending_port + "] = " + str(config[ACCEPTED_PEERS][str_pending][str_raw_pos][pending_port]))
            print("NODE ALREADY ASSIGNED IN THIS QUORUM, SKIPPING")

            try:
                config[PENDING_PEERS][pending_quorum].remove(pending_port)
            except ValueError:
                pass

            offset += 1
            return config, offset, intersections_made

        except KeyError as err:
            try: 
                check = (config[ACCEPTED_PEERS][str_pending][str_raw_pos])
            except KeyError as err:
                try:
                    check = (config[ACCEPTED_PEERS][str_pending])
                except KeyError as err:
                    pass
                config[ACCEPTED_PEERS][str_pending] = {}
                config[ACCEPTED_PEERS][str_pending][str_raw_pos] = {}
                #continue
            except KeyError:
                pass

        print("[" + str(config[API_PORT]) + "] Before CPA with stats:\nStrPos:\t" + str_pos + "\tPQ:\t" + str_pending + "\toffset:\t" + str(offset) + "\nNetwork size: " + str(config[NETWORK_SIZE]) + "\tPending\t" + str(config[PENDING_PEERS]) + "\tAccepted\t" + str(config[ACCEPTED_PEERS]) + "\n")

        #found, config = check_pending_assigned(config, str_raw_pos, str_pending, pending_port, self_a, self_b)

        config = activate_new_quorum(config, pending_port, str_raw_pos, str_pending, self_a, self_b, True)

        # Quorum activation caused an intersection spinup and the quorum is no longer in consideration
        if pending_port not in config[PENDING_PEERS][str_pending]:
            intersections_made += 1
            offset += 1
            print("SUCCESSFULLY SPUN UP INTERSECTION")
    else:
        for i in range(0, num_pending):
            config = activate_new_quorum(config, pending_port, str(i), str_pending, self_a, self_b, False)
    
    pending_pos += offset

    if intersections_made >= num_pending:
        config[NETWORK_SIZE] += 1

    print("[" + str(config[API_PORT]) + "] Left loop with stats:\nNetwork size: " + str(config[NETWORK_SIZE]) + "\tPending\t" + str(config[PENDING_PEERS]) + "\tAccepted\t" + str(config[ACCEPTED_PEERS]) + "\n")

    return config, offset, intersections_made

def process_pending_quorums(config, pending_quorum, joining_port, self_a, self_b):
    str_pending = str(pending_quorum)
    num_pending = int(pending_quorum)

    # Check for valid quorum
    try:
        t = config[PENDING_PEERS][pending_quorum]
    except KeyError:
        # Bad quorum requested
        return config

    config[PENDING_PEERS][pending_quorum].append(str(joining_port))

    print(config[PENDING_PEERS][pending_quorum]) 
    print(str_pending)

    # Number of new quorums made so far
    already_accepted = 0

    # Number of nodes we've spun up
    intersections_made = 0

    try:
        already_accepted = len(config[ACCEPTED_PEERS][pending_quorum])
    except KeyError:
        pass

    quorums_needed = int(pending_quorum) - already_accepted

    print("FOUND ALREADY_ACCEPTED " + str(already_accepted))
    print("FOUND QUORUMS_NEEDED " + str(quorums_needed))

    if len(config[PENDING_PEERS][pending_quorum]) >= quorums_needed:

        print("Found enough pending peers to make new quorum!")
        print("Attempting to make quorum with " + pending_quorum)

        pending_pos = 0
        offset = 0

        while (pending_pos < len(config[PENDING_PEERS][pending_quorum])) and (intersections_made < num_pending):
            config, offset, intersections_made = pending_quorum_loop(config, pending_pos, pending_quorum, offset, intersections_made, self_a, self_b)
            pending_pos += offset
            
            
    else:
        print("not enough pending peers for a new quorum!")
        print("Pending peers: " + str(len(config[PENDING_PEERS][pending_quorum])))
        print(config[PENDING_PEERS][pending_quorum])

        print("Peers needed for new quorum: " + str(quorums_needed))

    config = notify_neighbors_pending_peer(config, str(joining_port))
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

        peers[port].app.api.config = refresh_config_remote(peers[port].app.api.config, QUORUMS, port)

    return peers
