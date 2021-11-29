import json

from src.api.constants import NEIGHBOURS, PBFT_INSTANCES, QUORUMS, ROUTE_EXECUTED_CORRECTLY, PORT, QUORUM_ID, QUORUM_MEMBERS
from src.api.constants import ROUTE_EXECUTION_FAILED, API_IP, VALIDATOR_KEY, USER_KEY, DOCKER_IP
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.structures import Transaction
from src.api.api_util import forward, create_intersection_map, merge_intersection_maps
from flask import jsonify, request
import socket
import requests

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
        instance_a = SawtoothContainer()
        instance_b = SawtoothContainer()
        app.config[PBFT_INSTANCES] = Intersection(instance_a, instance_b, quorum_id_a, quorum_id_b)
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
        ips = [n.pop(DOCKER_IP) for n in app.config[QUORUMS][quorum_id]]
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

        app.logger.info("Adding quorum ID {q} with neighbours {n}".format(q=quorum_id, n=neighbours))
        # store neighbour info in app
        app.config[QUORUMS][quorum_id] = neighbours
        return ROUTE_EXECUTED_CORRECTLY


    @app.route('/quoruminfo/', methods=['POST'])
    def quoruminfo():
        if app.config[QUORUMS]:
            res_json = json.loads(json.dumps({
                "neighbors": app.config[QUORUMS]
            }))
            return res_json
        else:
            return ROUTE_EXECUTION_FAILED
    
    # Recursively finds the quorums with the fewest intersections by joining intersection maps
    @app.route('/min+intersection')
    @app.route('/min+intersection/<int:depth>')
    def min_intersection(depth=0):
        # Find the current peers two quorum ids and sort them
        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b
        smaller_quorum_id = min(id_a, id_b)
        larger_quorum_id = max(id_a, id_b)

        # Use its list of neighbors to find all quroum ids (assuming there is at least 1 intersection)
        quorum_ids = list(set([peer[QUORUM_ID] for peer in app.config[QUORUMS][id_a]] + [id_a, id_b]))

        # Creates a blank intersection map of all quroum ids and adds its own IP and port where it belongs
        intersection_map = create_intersection_map(quorum_ids)
        intersection_map[smaller_quorum_id][larger_quorum_id][request.host] = 0

        if (depth < 2):
            # For each quorum the peer is in
            for quorum_id, neighbors in app.config[QUORUMS].items():
                # For every neighboring peer in the quorum
                for neighbor in neighbors:
                    # Find the neighbors intersection map at a depth one higher and merge it with our current one
                    res = requests.get(f"http://{neighbor[API_IP]}:{neighbor[PORT]}/min+intersection/{depth+1}")
                    neighbor_map = json.loads(res.text)
                    intersection_map = merge_intersection_maps(intersection_map, neighbor_map)
        
        if (depth == 0): # Base call, find the minimum intersection using the completed itersection map and return the quorum ids
            min_quorum_id_a = None
            min_quorum_id_b = None
            min_peers = -1
            for row_id, row in intersection_map.items():
                for column_id, peer_set in row.items():
                    if len(peer_set) < min_peers or min_peers == -1:
                        min_peers = len(peer_set)
                        min_quorum_id_a = row_id
                        min_quorum_id_b = column_id
            return jsonify([min_quorum_id_a, min_quorum_id_b])
        else: # Recursive call, return the peer's intersection map
            return jsonify(intersection_map)
    
    # Requests to join the network in the minimum intersecting quorums
    @app.route('/request+join', methods=['POST'])
    def request_join():
        # Find the minimum intersection
        res_json = requests.post(f"http://{request.host}/min+intersection")

        # Get the caller's IP and port, join them to the minimum quorums
        req_json = request.get_json()
        requests.post(f"http://{req_json[API_IP]}:{req_json[PORT]}/join/{res_json[0]}")
        requests.post(f"http://{req_json[API_IP]}:{req_json[PORT]}/join/{res_json[1]}")
        
        return ROUTE_EXECUTED_CORRECTLY


    # remove neighbor from API after it leaves
    @app.route('/remove/<remove_port>', methods=['POST'])
    def remove(remove_port=None):
        req = get_json(request, app)

        app.logger.info("Removing {q} from node {n}".format(q=remove_port, n=app))

        for committee_id in app.config[QUORUMS]:
            index = 0
            for neighbor in app.config[QUORUMS][committee_id]:
                if str(neighbor[PORT]) == str(remove_port):
                    del app.config[QUORUMS][committee_id][index]
                index += 1

        return ROUTE_EXECUTED_CORRECTLY

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
            return forward(app, "make+genesis/{id}".format(id=quorum_id), quorum_id, req)
        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/submit/', methods=['POST'])
    def submit():
        req = get_json(request, app)
        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            app.config[PBFT_INSTANCES].submit(tx)
            return ROUTE_EXECUTED_CORRECTLY
        else:
            return forward(app, "submit/", req[QUORUM_ID], req)

    @app.route('/get/', methods=['POST'])
    def get():
        req = get_json(request, app)

        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            return app.config[PBFT_INSTANCES].get_tx(tx)
        else:
            return forward(app, "get/", req[QUORUM_ID], req)

    @app.route('/blocks/', methods=['POST'])
    def blocks():
        req = get_json(request, app)
        if app.config[PBFT_INSTANCES].in_committee(req[QUORUM_ID]):
            return json.dumps(app.config[PBFT_INSTANCES].blocks(req[QUORUM_ID]))
        else:
            return forward(app, "blocks/", req[QUORUM_ID], req)

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

    @app.route('/ip/<quorum_id>')
    def ip(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return app.config[PBFT_INSTANCES].ip(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))
