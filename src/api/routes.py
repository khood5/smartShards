import json

from src.api.constants import NEIGHBOURS, PBFT_INSTANCES, QUORUMS, ROUTE_EXECUTED_CORRECTLY, PORT, QUORUM_ID, QUORUM_MEMBERS, MIN_QUORUM_PEERS
from src.api.constants import ROUTE_EXECUTION_FAILED, API_IP, VALIDATOR_KEY, USER_KEY, DOCKER_IP
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.structures import Transaction
from src.api.api_util import forward, create_intersection_map, merge_intersection_maps, insert_into_intersection_map
from flask import jsonify, request
import socket
import requests
import logging
import os

logging.basicConfig(
    format='%(asctime)s %(levelname)-2s %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
api_log = logging.getLogger(__name__)

LOG_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def api_log_to(path, console_logging=False):
    handler = logging.handlers.RotatingFileHandler(path, backupCount=5, maxBytes=LOG_FILE_SIZE)
    formatter = logging.Formatter('%(asctime)s %(levelname)-2s %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    api_log.propagate = console_logging
    api_log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
    api_log.addHandler(handler)

def get_json(request, app):
    # try and parse json
    try:
        req = request.get_json(force=True)
    except KeyError as e:
        app.logger.error(e)
        return ROUTE_EXECUTION_FAILED.format(msg=e)
    return req

def add_routes(app):
    # return info about the system flask is running on
    @app.route('/')
    @app.route('/info/')
    @app.route('/info/<quorum_id>')
    def info(quorum_id=None):
        ip = socket.gethostbyname(socket.gethostname())
        port = request.host.split(':')[1]
        if app.config[PBFT_INSTANCES] is not None:
            if app.config[PBFT_INSTANCES].in_committee(quorum_id):
                quorum_members = len(app.config[QUORUMS][quorum_id]) + 1
                system_info = {API_IP: ip, PORT: port, QUORUM_ID: quorum_id, QUORUM_MEMBERS: quorum_members}
                return jsonify(system_info)

        system_info = {API_IP: ip, PORT: port, QUORUM_ID: None}
        return jsonify(system_info)

    # stat sawtooth for quorum id
    @app.route('/start/<quorum_id_a>/<quorum_id_b>')
    def start(quorum_id_a=None, quorum_id_b=None):
        if app.config[PBFT_INSTANCES] is not None:
            app.logger.warning("peer has already started, restarting")
            del app.config[PBFT_INSTANCES]
        app.logger.info(f"Starting {request.host} on quorums {quorum_id_a} and {quorum_id_b}")
        instance_a = SawtoothContainer()
        instance_b = SawtoothContainer()
        app.config[PBFT_INSTANCES] = Intersection(instance_a, instance_b, quorum_id_a, quorum_id_b)
        app.config[QUORUMS] = {}
        app.config[QUORUMS][quorum_id_a] = []
        app.config[QUORUMS][quorum_id_b] = []
        return ROUTE_EXECUTED_CORRECTLY

    # joins pbft instance to a committee
    @app.route('/join/<quorum_id>', methods=['POST'])
    def join(quorum_id=None):
        req = get_json(request, app)
        neighbours = req[NEIGHBOURS]
        # try to access peer object (if peer is inaccessible then peer has not started)
        try:
            # check and make sure peer is in quorum
            if not app.config[PBFT_INSTANCES].in_committee(quorum_id):
                app.logger.error("Peer not in committee {} can not join PBFT".format(quorum_id))
                return ROUTE_EXECUTION_FAILED.format(msg="Peer not in committee {} can not join PBFT"
                                                     .format('quorum_id'))
        except AttributeError as e:
            app.logger.error("Peer not started request /start/<quorum_id_a>/<quorum_id_b> first")
            app.logger.error(e)
            return ROUTE_EXECUTION_FAILED.format(msg="") + "Peer not started request " \
                                                           "/start/<quorum_id_a>/<quorum_id_b> first \n\n\n{}".format(e)

        app.logger.info("Joining {q} with neighbours {n}".format(q=quorum_id, n=neighbours))
        # store neighbour info in app
        app.config[QUORUMS][quorum_id] = neighbours
        # get sawtooth container ip address
        ips = [n[DOCKER_IP] for n in app.config[QUORUMS][quorum_id]]
        ips.append(app.config[PBFT_INSTANCES].ip(quorum_id))
        app.config[PBFT_INSTANCES].peer_join(quorum_id, ips)  # use sawtooth container ip to start sawtooth
        return ROUTE_EXECUTED_CORRECTLY

    # adds neighbour info to API (does not add to sawtooth use join to join a peer to a network)
    @app.route('/add/<quorum_id>', methods=['POST'])
    def add(quorum_id=None):
        req = get_json(request, app)
        neighbours = req[NEIGHBOURS]
        # try to access peer object (if peer is inaccessible then peer has not started)
        try:
            # check and make sure peer is in quorum
            if not app.config[PBFT_INSTANCES].in_committee(quorum_id):
                app.logger.error("Peer not in committee {} can not join PBFT".format(quorum_id))
                return ROUTE_EXECUTION_FAILED.format(msg="Peer not in committee {} can not join PBFT"
                                                     .format('quorum_id'))
        except AttributeError as e:
            app.logger.error("Peer not started request /start/<quorum_id_a>/<quorum_id_b> first")
            app.logger.error(e)
            return ROUTE_EXECUTION_FAILED.format(msg="") + "Peer not started request " \
                                                           "/start/<quorum_id_a>/<quorum_id_b> first \n\n\n{}".format(
                e)

        app.logger.info("Adding quorum ID {q} to {host} with neighbours {n}".format(q=quorum_id, n=neighbours, host=request.host))
        # store neighbour info in app
        app.config[QUORUMS][quorum_id] = neighbours
        return ROUTE_EXECUTED_CORRECTLY

    # Get information about all of the members of a quorum
    # Return format 
    # { 
    #     quorum_id: [ 
    #         {API_IP, PORT, QUORUM_ID, DOCKER_IP},
    #         ...
    #     ],
    #     ... 
    # }
    @app.route('/quorum+info')
    @app.route('/quorum+info/<quorum_id>')
    def quorum_info(quorum_id=None):

        # If the user did not specify a quorum id, return all quorums
        if quorum_id is None:
            quorum_ids = list(app.config[QUORUMS].keys())
        else:
            quorum_ids = [quorum_id]

        # If the user does not specify, include ourselves in the quorum info
        include_self = request.args.get("include_self", "true") == "true"

        logging.info(f"{request.host} called quorum+info with quorum_ids={quorum_ids} and include_self={include_self}")
        
        # Create the eventual response dictionary
        res = {}

        # For every quorum that we are supposed to return
        for quorum_id in quorum_ids:

            # Make sure that we are in the quorum, otherwise fail
            if app.config[PBFT_INSTANCES].in_committee(quorum_id):

                # Copy over our neighbor info into the response dictionary
                res[quorum_id] = [peer for peer in app.config[QUORUMS][quorum_id]]

                # If we are supposed to include ourself, add our info to it
                if include_self:
                    host_ip = request.host.split(":")[0]
                    host_port = str(app.config[PORT])
                    host_other_quorum_id = [possible_quorum_id for possible_quorum_id in app.config[QUORUMS].keys() if possible_quorum_id != quorum_id][0]
                    host_docker_ip = app.config[PBFT_INSTANCES].ip(quorum_id)
                    res[quorum_id].append({API_IP: host_ip, PORT: host_port, QUORUM_ID: host_other_quorum_id, DOCKER_IP: host_docker_ip})
            else:
                return ROUTE_EXECUTION_FAILED.format(msg=f"{request.host} is not in quorum {quorum_id}")

        # Return the completed response dictionary
        return res
    
    # Get an intersection map of the whole network
    # Return format
    # { 
    #     0: {1: {HOST: 0, ...}, 2: {HOST: 0, ...}, ...},
    #     1: {2: {HOST: 0, ...}, ...}, ...
    # }
    @app.route('/intersection+map')
    def intersection_map():

        # Get our quorum ids
        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b

        # Figure out the list of all quorum ids and sort them
        quorum_ids = list(set([peer[QUORUM_ID] for peer in app.config[QUORUMS][id_a]] + [id_a, id_b]))
        quorum_ids.sort()

        # Create an intersection map with the ids and insert ourselves into it
        intersection_map = create_intersection_map(quorum_ids)
        insert_into_intersection_map(intersection_map, request.host, id_a, id_b)

        # For each direct neighbor we have, insert them into the intersection map
        for quorum, peers in app.config[QUORUMS].items():
            for peer in peers:
                insert_into_intersection_map(intersection_map, f"{peer[API_IP]}:{peer[PORT]}", quorum, peer[QUORUM_ID])

        # Some setup to minimize the number of requests done
        known_quorums = [id_a, id_b]

        # For each neighbor in our quorum a
        for peer in app.config[QUORUMS][id_a]:

            # Figure out its other quorum
            other_quorum = peer[QUORUM_ID]

            # If we don't already have info about that quorum
            if other_quorum not in known_quorums:

                # Ask for that peer's quorum info
                res = requests.get(f"http://{peer[API_IP]}:{peer[PORT]}/quorum+info", headers={"Connection":"close"})
                peer_neighbors = res.json()

                # For every peer in the other quorum, add it to the intersection map
                for peer in peer_neighbors[other_quorum]:
                    insert_into_intersection_map(intersection_map, f"{peer[API_IP]}:{peer[PORT]}", other_quorum, peer[QUORUM_ID])
                
                # We just learned about other quorum, so add it to the list of known quorums
                known_quorums.append(other_quorum)

        # Return the completed intersection map
        return jsonify(intersection_map)
    
    # Finds the first intersection that has the fewest peers
    # Return format
    # {
    #     min_intersection: [min_quorum_id_a, min_quorum_id_b],
    #     peers: {HOST: 0, ...}
    # }
    @app.route('/min+intersection')
    def min_intersection():

        # Get a map of the whole network
        intersection_map = requests.get(f"http://{request.host}/intersection+map", headers={"Connection":"close"}).json()

        # Perform some setup for comparisons
        min_quorum_id_a = None
        min_quorum_id_b = None
        min_peers = -1

        # For every intersection i
        for row_id, row in intersection_map.items():
            for column_id, peer_set in row.items():

                # If there are fewer peers in i than the previous min
                if len(peer_set) < min_peers or min_peers == -1:

                    # Set the new min intersection
                    min_peers = len(peer_set)
                    min_quorum_id_a = row_id
                    min_quorum_id_b = column_id

        # Return the intersection and the peers in it
        return jsonify({
            "min_intersection": [min_quorum_id_a, min_quorum_id_b],
            "peers": intersection_map[min_quorum_id_a][min_quorum_id_b]
        })
    
    # Finds the first intersection that has the most peers
    # Return format
    # {
    #     max_intersection: [max_quorum_id_a, max_quorum_id_b],
    #     peers: {HOST: 0, ...}
    # }
    @app.route('/max+intersection')
    def max_intersection():

        # Get a map of the whole network
        intersection_map = requests.get(f"http://{request.host}/intersection+map", headers={"Connection":"close"}).json()

        # Perform some setup for comparisons
        max_quorum_id_a = None
        max_quorum_id_b = None
        max_peers = -1

        # For every intersection i
        for row_id, row in intersection_map.items():
            for column_id, peer_set in row.items():

                # If there are fewer peers in i than the previous min
                if len(peer_set) > max_peers or max_peers == -1:

                    # Set the new min intersection
                    max_peers = len(peer_set)
                    max_quorum_id_a = row_id
                    max_quorum_id_b = column_id

        # Return the intersection and the peers in it
        return jsonify(
            {
                "max_intersection": [max_quorum_id_a, max_quorum_id_b],
                "peers": intersection_map[max_quorum_id_a][max_quorum_id_b]
            })
    
    # Requests to join the network in the minimum intersecting quorums
    @app.route('/request+join', methods=['POST'])
    def request_join():

        # Get the known host passed into the request
        req = get_json(request, app)
        known_host = req["known_host"]

        # Find the minimum intersection that we should join
        res = requests.get(f"http://{known_host}/min+intersection", headers={"Connection":"close"}).json()
        
        # Save its info into some variables
        min_intersection = res["min_intersection"]

        min_intersection_peers = list(res["peers"].keys())
        min_peer = min_intersection_peers[0]

        min_id_a = min_intersection[0]
        min_id_b = min_intersection[1]
        
        # Get the neighbors of the min intersection
        min_intersection_neighbors = requests.get(f"http://{min_peer}/quorum+info", headers={"Connection":"close"}).json()

        # Store the neighbors for joining
        join_a_json = min_intersection_neighbors[min_id_a]
        join_b_json = min_intersection_neighbors[min_id_b]

        # Start the new peer and join each of the min quorums
        requests.get(f"http://localhost:{app.config[PORT]}/start/{min_id_a}/{min_id_b}", headers={"Connection":"close"})
        requests.post(f"http://localhost:{app.config[PORT]}/join/{min_id_a}", json={NEIGHBOURS: join_a_json}, headers={"Connection":"close"})
        requests.post(f"http://localhost:{app.config[PORT]}/join/{min_id_b}", json={NEIGHBOURS: join_b_json}, headers={"Connection":"close"})

        # Collect the new peer's info for adding it to its neighbor APIs in min quorum a
        peer_json_a = {
            "host": request.host,
            "host_quorum": min_id_b,
            "quorum": min_id_a,
            "docker_ip": app.config[PBFT_INSTANCES].ip(min_id_a)
        }

        # For every peer in min quorum a, add the new peer as a neighbor
        for peer in min_intersection_neighbors[min_id_a]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json=peer_json_a, headers={"Connection":"close"})
        
        # Collect the new peer's info for adding it to its neighbor APIs in min quorum b
        peer_json_b = {
            "host": request.host,
            "host_quorum": min_id_a,
            "quorum": min_id_b,
            "docker_ip": app.config[PBFT_INSTANCES].ip(min_id_b)
        }

        # For every peer in min quorum b, add the new peer as a neighbor
        for peer in min_intersection_neighbors[min_id_b]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json=peer_json_b, headers={"Connection":"close"})

        # Use the min peer to add the new peer's a sawtooth as a validator
        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": min_id_a,
            "val_key": app.config[PBFT_INSTANCES].val_key(min_id_a)
        }, headers={"Connection":"close"})

        # Use the min peer to add the new peer's b sawtooth as a validator
        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": min_id_b,
            "val_key": app.config[PBFT_INSTANCES].val_key(min_id_b)
        }, headers={"Connection":"close"})

        return ROUTE_EXECUTED_CORRECTLY
    
    # Requests to leave the network and be replaced by a peer from the maximum intersecting quorums
    @app.route('/request+leave', methods=['POST'])
    def request_leave():

        # Find our quorums
        self_id_a = app.config[PBFT_INSTANCES].committee_id_a
        self_id_b = app.config[PBFT_INSTANCES].committee_id_b

        # Find the max intersection so we know where to take from
        res = requests.get(f"http://{request.host}/max+intersection", headers={"Connection":"close"}).json()
        max_intersection = res["max_intersection"]
        max_intersection_peers = list(res["peers"].keys())

        # This is our replacement
        max_peer = max_intersection_peers[0]

        # And these are its quorums
        max_id_a = max_intersection[0]
        max_id_b = max_intersection[1]

        # If the max intersection is not our intersection we have to add a peer from it to our own
        if self_id_a != max_id_a or self_id_b != max_id_b:
        
            # We want to get all of its neighbors, not including itself so as to not remove itself from itself later
            max_intersection_neighbors = requests.get(f"http://{max_peer}/quorum+info?include_self=false", headers={"Connection":"close"}).json()

            # Check to see if we can remove it while still maintaining validity
            a_below = len(max_intersection_neighbors[max_id_a])+1 <= 7
            b_below = len(max_intersection_neighbors[max_id_b])+1 <= 7

            # If not, return a failure
            if a_below or b_below:
                return ROUTE_EXECUTION_FAILED.format(msg=f"A peer leaving the max intersection ({max_id_a}-{max_id_b}) would invalidate {max_id_a if a_below else ''}{' and ' if a_below and b_below else ''}{max_id_b if b_below else ''}")
            
            # Remove the replacement from its neighbors APIs in max quorum a
            for peer in max_intersection_neighbors[max_id_a]:
                requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/remove+host", json={"host": max_peer}, headers={"Connection":"close"})
            
            # Remove the replacement from its neighbors APIs in max quorum b
            for peer in max_intersection_neighbors[max_id_b]:
                requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/remove+host", json={"host": max_peer}, headers={"Connection":"close"})

            # Remove the replacement from its neighbors sawtooths in max quorum a
            requests.post(f"http://{max_peer}/remove+validator", json={
                "quorum_id": max_id_a,
                "val_key": requests.get(f"http://{max_peer}/val+key/{max_id_a}", headers={"Connection":"close"}).text
            }, headers={"Connection":"close"})

            # Remove the replacement from its neighbors sawtooths in max quorum b
            requests.post(f"http://{max_peer}/remove+validator", json={
                "quorum_id": max_id_b,
                "val_key": requests.get(f"http://{max_peer}/val+key/{max_id_b}", headers={"Connection":"close"}).text
            }, headers={"Connection":"close"})

            # Now that our replacement is floating in the void, we can have it take our place

            # Find our new neighbors and quorums
            self_intersection_peers = requests.get(f"http://{request.host}/quorum+info", headers={"Connection":"close"}).json()
            self_id_a = app.config[PBFT_INSTANCES].committee_id_a
            self_id_b = app.config[PBFT_INSTANCES].committee_id_b

            # This is the JSON needed to join the replacement's API
            join_a_json = self_intersection_peers[self_id_a]
            join_b_json = self_intersection_peers[self_id_b]

            # Start the replacement in the new quorums and join it
            requests.get(f"http://{max_peer}/start/{self_id_a}/{self_id_b}", headers={"Connection":"close"})
            requests.post(f"http://{max_peer}/join/{self_id_a}", json={NEIGHBOURS: join_a_json}, headers={"Connection":"close"})
            requests.post(f"http://{max_peer}/join/{self_id_b}", json={NEIGHBOURS: join_b_json}, headers={"Connection":"close"})

            # Collect the replacement peer's info for adding it to its neighbor APIs in self quorum a
            replacement_json_a = {
                "host": max_peer, 
                "host_quorum": self_id_b, 
                "quorum": self_id_a, 
                "docker_ip": requests.get(f"http://{max_peer}/ip/{self_id_a}", headers={"Connection":"close"}).text
            }

            # Add the replacement to every neighbor's API in self quorum a
            for peer in self_intersection_peers[self_id_a]:
                requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json=replacement_json_a, headers={"Connection":"close"})
            
            # Collect the replacement peer's info for adding it to its neighbor APIs in self quorum b
            replacement_json_b = {
                "host": max_peer, 
                "host_quorum": self_id_a, 
                "quorum": self_id_b, 
                "docker_ip": requests.get(f"http://{max_peer}/ip/{self_id_b}", headers={"Connection":"close"}).text
            }

            # Add the replacement to every neighbor's API in self quorum b
            for peer in self_intersection_peers[self_id_b]:
                requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json=replacement_json_b, headers={"Connection":"close"})

            # Add the replacement to every neighbor's sawtooth in self quorum a
            requests.post(f"http://{request.host}/add+validator", json={
                "quorum_id": self_id_a,
                "val_key": requests.get(f"http://{max_peer}/val+key/{self_id_a}", headers={"Connection":"close"}).text
            }, headers={"Connection":"close"})

            # Add the replacement to every neighbor's sawtooth in self quorum b
            requests.post(f"http://{request.host}/add+validator", json={
                "quorum_id": self_id_b,
                "val_key": requests.get(f"http://{max_peer}/val+key/{self_id_b}", headers={"Connection":"close"}).text
            }, headers={"Connection":"close"})
        
        # By this point the replacement is in our quorum, so we can remove ourself

        # Find our neighbors
        self_intersection_neighbors = requests.get(f"http://{request.host}/quorum+info?include_self=false", headers={"Connection":"close"}).json()

        # Remove ourself from our neighbors APIs in self quorum a
        for peer in self_intersection_neighbors[self_id_a]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/remove+host", json={"host": f"{request.host}"}, headers={"Connection":"close"})
        
        # Remove ourself from our neighbors APIs in self quorum b
        for peer in self_intersection_neighbors[self_id_b]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/remove+host", json={"host": f"{request.host}"}, headers={"Connection":"close"})

        # Remove ourself from our neighbors Sawtooths in self quorum a
        requests.post(f"http://{request.host}/remove+validator", json={
            "quorum_id": self_id_a,
            "val_key": app.config[PBFT_INSTANCES].val_key(self_id_a)
        }, headers={"Connection":"close"})

        # Remove ourself from our neighbors Sawtooths in self quorum b
        requests.post(f"http://{request.host}/remove+validator", json={
            "quorum_id": self_id_b,
            "val_key": app.config[PBFT_INSTANCES].val_key(self_id_b)
        }, headers={"Connection":"close"})

        app.config[QUORUMS] = {}
        del app.config[PBFT_INSTANCES]

        return ROUTE_EXECUTED_CORRECTLY
    
    # Add neighbor from API when it joins
    @app.route('/add+host', methods=['POST'])
    def add_host():

        # Get info about the host that we are about to add
        req = get_json(request, app)
        host = req["host"]
        host_quorum = req["host_quorum"]
        quorum = req["quorum"]
        docker_ip = req["docker_ip"]

        # Collect the host info into a add-friendly format
        split_host = host.split(":")
        host_json = {
            API_IP: split_host[0],
            PORT: split_host[1],
            QUORUM_ID: host_quorum,
            DOCKER_IP: docker_ip
        }

        logging.info(f"Adding host {host} to {request.host}'s API neighbors")

        # Append the host info to the quorum
        app.config[QUORUMS][quorum].append(host_json)
            
        logging.info(f"Host {host} added to {request.host}'s API neighbors")
        return ROUTE_EXECUTED_CORRECTLY

    # remove neighbor from API after it leaves
    @app.route('/remove+host', methods=['POST'])
    def remove_host():

        # Get info about the host that we are about to remove
        req = get_json(request, app)
        host = req["host"]

        logging.info(f"Removing host {host} from {request.host}'s API neighbors")

        # Remove the host info from the quorum
        for quorum in app.config[QUORUMS]:
            app.config[QUORUMS][quorum] = [neighbor for neighbor in app.config[QUORUMS][quorum] if (f"{neighbor[API_IP]}:{neighbor[PORT]}" != host)]
        
        logging.info(f"Host {host} removed from {request.host}'s API neighbors")
        return ROUTE_EXECUTED_CORRECTLY
    
    # add a validator to the quorum
    @app.route('/add+validator', methods=['POST'])
    def add_validator():

        # Get info about the validator that we are about to add
        req = get_json(request, app)
        quorum_id = req["quorum_id"]
        add_val_key = req["val_key"]

        logging.info(f"Trying to add validator {add_val_key} to quorum {quorum_id}")

        # Store the intersection in a variable for clarity
        intersection = app.config[PBFT_INSTANCES]

        # Make sure that we are in the quorum, error if not
        if intersection.in_committee(quorum_id):

            # Get all of the current val keys, add the new one
            val_keys = intersection.get_committee_val_keys(quorum_id)
            val_keys.append(add_val_key)

            # Try to update the committee attempts_left times, error if failed
            attempts_left = 5

            # While we still have attempts left
            while attempts_left > 0:

                # If the update was successful, log it and return
                logging.info(f"Trying to add {add_val_key} to quorum {quorum_id}, attempts left = {attempts_left}")
                if intersection.update_committee(quorum_id, val_keys):
                    logging.info(f"Validator {add_val_key} added to quorum {quorum_id}!")
                    return ROUTE_EXECUTED_CORRECTLY
                
                # Decrement the number of attempts left
                attempts_left -= 1
            
            logging.error(f"Peer {request.host} could not add validator {add_val_key} to quorum {quorum_id}!")
            return ROUTE_EXECUTION_FAILED.format(msg="Committee update failed!")
        else:
            logging.error(f"Peer {request.host} not in quorum {quorum_id}!")
            return ROUTE_EXECUTION_FAILED.format(msg=f"Peer {request.host} not in quorum {quorum_id}")
    
    # remove a validator from the quorum
    @app.route('/remove+validator', methods=['POST'])
    def remove_validator():

        # Get info about the validator that we are about to add
        req = get_json(request, app)
        quorum_id = req["quorum_id"]
        remove_val_key = req["val_key"]

        logging.info(f"Trying to remove validator {remove_val_key} from quorum {quorum_id}")

        # Store the intersection in a variable for clarity
        intersection = app.config[PBFT_INSTANCES]

        # Make sure that we are in the quorum, error if not
        if intersection.in_committee(quorum_id):

            # Get all of the current val keys, remove the one to be removed
            val_keys = intersection.get_committee_val_keys(quorum_id)

            if remove_val_key not in val_keys:
                logging.error(f"Validator {remove_val_key} not found in committee {quorum_id}'s validator keys!")
                return ROUTE_EXECUTION_FAILED.format(msg=f"Validator {remove_val_key} not found in committee {quorum_id}'s validator keys!")

            val_keys.remove(remove_val_key)

            # Try to update the committee attempts_left times, error if failed
            attempts_left = 5

            # While we still have attempts left
            while attempts_left > 0:

                # If the update was successful, log it and return
                logging.info(f"Trying to remove {remove_val_key} from quorum {quorum_id}, attempts left = {attempts_left}")
                if intersection.update_committee(quorum_id, val_keys):
                    logging.info(f"Validator {remove_val_key} removed from quorum {quorum_id}!")
                    return ROUTE_EXECUTED_CORRECTLY
                
                # Decrement the number of attempts left
                attempts_left -= 1
            
            logging.error(f"Peer {request.host} could not remove validator {remove_val_key} from quorum {quorum_id}!")
            return ROUTE_EXECUTION_FAILED.format(msg="Committee update failed!")
        else:
            logging.error(f"Peer {request.host} not in quorum {quorum_id}!")
            return ROUTE_EXECUTION_FAILED.format(msg=f"Peer {request.host} not in quorum {quorum_id}")
        

    # request that genesis be made
    @app.route('/make+genesis/<quorum_id>', methods=['POST'])
    def make_genesis(quorum_id=None):
        req = get_json(request, app)
        val_keys = req[VALIDATOR_KEY]
        usr_keys = req[USER_KEY]
        if quorum_id == app.config[PBFT_INSTANCES].committee_id_a:
            app.config[PBFT_INSTANCES].make_genesis(quorum_id, val_keys, usr_keys)
        elif quorum_id == app.config[PBFT_INSTANCES].committee_id_b:
            app.config[PBFT_INSTANCES].make_genesis(quorum_id, val_keys, usr_keys)
        else:
            return forward(app, "/make+genesis/{id}".format(id=quorum_id), quorum_id, req)
        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/submit', methods=['POST'])
    def submit():
        req = get_json(request, app)
        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            app.config[PBFT_INSTANCES].submit(tx)
            return ROUTE_EXECUTED_CORRECTLY
        else:
            return forward(app, "/submit", req[QUORUM_ID], req)

    @app.route('/get', methods=['POST'])
    def get():
        req = get_json(request, app)

        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            return app.config[PBFT_INSTANCES].get_tx(tx)
        else:
            return forward(app, "/get", req[QUORUM_ID], req)

    @app.route('/blocks', methods=['POST'])
    def blocks():
        req = get_json(request, app)
        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            return json.dumps(app.config[PBFT_INSTANCES].blocks(req[QUORUM_ID]))
        else:
            return forward(app, "/blocks", req[QUORUM_ID], req)

    @app.route('/user+key/<quorum_id>')
    def usr_key(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return app.config[PBFT_INSTANCES].user_key(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/val+key/<quorum_id>')
    def val_key(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return app.config[PBFT_INSTANCES].val_key(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/committee+val+keys/<quorum_id>')
    def committee_val_keys(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return jsonify(app.config[PBFT_INSTANCES].get_committee_val_keys(quorum_id))
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/ip/<quorum_id>')
    def ip(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return app.config[PBFT_INSTANCES].ip(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/committee+ips/<quorum_id>')
    def committee_ips(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return jsonify(app.config[PBFT_INSTANCES].get_committee_ips(quorum_id))
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))
