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
    # returns 
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
        if quorum_id is None:
            quorum_ids = list(app.config[QUORUMS].keys())
        else:
            quorum_ids = [quorum_id]

        print(f"{request.host} called quorum+info with quorums={quorum_ids}")
        
        res = {}

        for quorum_id in quorum_ids:
            if app.config[PBFT_INSTANCES].in_committee(quorum_id):
                res[quorum_id] = [peer for peer in app.config[QUORUMS][quorum_id]]
                host_ip = request.host.split(":")[0]
                host_port = str(app.config[PORT])
                host_other_quorum_id = [possible_quorum_id for possible_quorum_id in app.config[QUORUMS].keys() if possible_quorum_id != quorum_id][0]
                host_docker_ip = app.config[PBFT_INSTANCES].ip(quorum_id)
                res[quorum_id].append({API_IP: host_ip, PORT: host_port, QUORUM_ID: host_other_quorum_id, DOCKER_IP: host_docker_ip})
            else:
                return ROUTE_EXECUTION_FAILED.format(msg=f"Peer is not in quorum {quorum_id}")
        
        return res
    
    @app.route('/intersection+map')
    def intersection_map():
        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b

        quorum_ids = list(set([peer[QUORUM_ID] for peer in app.config[QUORUMS][id_a]] + [id_a, id_b]))
        quorum_ids.sort()
        print(f"the quorum ids are {quorum_ids}")

        intersection_map = create_intersection_map(quorum_ids)

        insert_into_intersection_map(intersection_map, request.host, id_a, id_b)

        for quorum, peers in app.config[QUORUMS].items():
            for peer in peers:
                print(f"adding {peer[API_IP]}:{peer[PORT]} to quorum {quorum} (layer 1)")
                insert_into_intersection_map(intersection_map, f"{peer[API_IP]}:{peer[PORT]}", quorum, peer[QUORUM_ID])

        for peer in app.config[QUORUMS][id_a]:
            res = requests.get(f"http://{peer[API_IP]}:{peer[PORT]}/quorum+info")
            peer_neighbors = res.json()
            other_quorum = {quorum: neighbors for quorum, neighbors in peer_neighbors.items() if quorum != id_a}
            for quorum, neighbors in other_quorum.items():
                for peer in neighbors:
                    print(f"adding {peer[API_IP]}:{peer[PORT]} to quorum {quorum} (layer 2)")
                    insert_into_intersection_map(intersection_map, f"{peer[API_IP]}:{peer[PORT]}", quorum, peer[QUORUM_ID])
        
        print("intersection map looks like:")
        print(intersection_map)

        return jsonify(intersection_map)
    
    # Recursively finds the quorums with the fewest intersections by joining intersection maps
    @app.route('/min+intersection')
    def min_intersection():
        intersection_map = requests.get(f"http://{request.host}/intersection+map").json()
        min_quorum_id_a = None
        min_quorum_id_b = None
        min_peers = -1
        for row_id, row in intersection_map.items():
            for column_id, peer_set in row.items():
                if len(peer_set) < min_peers or min_peers == -1:
                    min_peers = len(peer_set)
                    min_quorum_id_a = row_id
                    min_quorum_id_b = column_id
        return jsonify(
            {
                "min_intersection": [min_quorum_id_a, min_quorum_id_b],
                "peers": intersection_map[min_quorum_id_a][min_quorum_id_b]
            })
    
    # Requests to join the network in the minimum intersecting quorums
    @app.route('/request+join', methods=['POST'])
    def request_join():
        req_json = request.get_json()
        known_host = req_json["known_host"]
        # Find the minimum intersection
        res = requests.get(f"http://{known_host}/min+intersection").json()
        min_intersection = res["min_intersection"]
        min_intersection_peers = list(res["peers"].keys())
        min_peer = min_intersection_peers[0]

        id_a = min_intersection[0]
        id_b = min_intersection[1]
        
        min_intersection_neighbors = requests.get(f"http://{min_peer}/quorum+info").json()

        join_a_json = min_intersection_neighbors[id_a]
        join_b_json = min_intersection_neighbors[id_b]

        requests.get(f"http://localhost:{app.config[PORT]}/start/{id_a}/{id_b}")
        requests.post(f"http://localhost:{app.config[PORT]}/join/{id_a}", json={NEIGHBOURS: join_a_json})
        requests.post(f"http://localhost:{app.config[PORT]}/join/{id_b}", json={NEIGHBOURS: join_b_json})

        print("AFTER JOINING THE QUORUMS LOOKS LIKE")
        print(app.config[QUORUMS])
        
        for peer in min_intersection_neighbors[id_a]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json={"host": f"{request.host}", "host_quorum": id_b, "quorum": id_a, "docker_ip": app.config[PBFT_INSTANCES].ip(id_a)})
        
        for peer in min_intersection_neighbors[id_b]:
            requests.post(f"http://{peer[API_IP]}:{peer[PORT]}/add+host", json={"host": f"{request.host}", "host_quorum": id_a, "quorum": id_b, "docker_ip": app.config[PBFT_INSTANCES].ip(id_b)})

        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": id_a,
            "val_key": app.config[PBFT_INSTANCES].val_key(id_a)
        })

        requests.post(f"http://{min_peer}/add+validator", json={
            "quorum_id": id_b,
            "val_key": app.config[PBFT_INSTANCES].val_key(id_b)
        })

        return ROUTE_EXECUTED_CORRECTLY
    
    # Recursively finds the quorums with the fewest intersections by joining intersection maps
    @app.route('/max+intersection')
    @app.route('/max+intersection/<int:depth>')
    def max_intersection(depth=0):
        intersection_map = requests.get(f"http://{request.host}/intersection+map").json()
        max_quorum_id_a = None
        max_quorum_id_b = None
        max_peers = -1
        for row_id, row in intersection_map.items():
            for column_id, peer_set in row.items():
                if len(peer_set) > max_peers or max_peers == -1:
                    max_peers = len(peer_set)
                    max_quorum_id_a = row_id
                    max_quorum_id_b = column_id
        return jsonify(
            {
                "max_intersection": [max_quorum_id_a, max_quorum_id_b],
                "peers": intersection_map[max_quorum_id_a][max_quorum_id_b]
            })
    
    # Requests to leave the network and be replaced by a node from the maximum intersecting quorums
    @app.route('/request+leave', methods=['POST'])
    def request_leave():
        # Find the maximum intersection
        res_json = requests.post(f"http://{request.host}/max+intersection")
        max_intersection_a = res_json["max_intersection"][0]
        max_intersection_b = res_json["max_intersection"][1]
        max_intersection_peers = res_json["peers"]

        id_a = app.config[PBFT_INSTANCES].committee_id_a
        neighbors_a = app.config[QUORUMS][id_a]
        id_b = app.config[PBFT_INSTANCES].committee_id_b
        neighbors_b = app.config[QUORUMS][id_b]

        if (max_intersection_a != id_a or max_intersection_b != id_b):
            for peer in res_json['peers'].keys():
                res = requests.post(f"http://{peer}/change+quorums", json={"req_id_a": id_a, "neighbors_a": neighbors_a, "req_id_b": id_b, "neighbors_b": neighbors_b})
                if res == ROUTE_EXECUTED_CORRECTLY:
                    break
            else:
                return ROUTE_EXECUTION_FAILED.format(msg=f"Nobody from {max_intersection_a}-{max_intersection_b} could replace current node")

        # code to actually leave the quorum
        
        return ROUTE_EXECUTED_CORRECTLY
    
    @app.route('/change+quorums', methods=['POST'])
    def change_quorums():
        req = get_json(request, app)

        intersection = app.config[PBFT_INSTANCES]

        id_a = intersection.committee_id_a
        id_b = intersection.committee_id_b

        val_key_a = intersection.val_key(id_a)
        val_key_b = intersection.val_key(id_b)

        quorum_a_val_keys = intersection.get_peers(id_a)
        quorum_b_val_keys = intersection.get_peers(id_b)

        # If leaving will keep current quorums in a stable state
        if (len(quorum_a_val_keys) - 1 >= MIN_QUORUM_PEERS and len(quorum_b_val_keys) - 1 >= MIN_QUORUM_PEERS):
            quorum_a_val_keys.remove(val_key_a)
            quorum_b_val_keys.remove(val_key_b)

            intersection.update_committee(id_a, quorum_a_val_keys)
            intersection.update_committee(id_b, quorum_b_val_keys)

            for committee_id in app.config[QUORUMS]:
                for neighbor in app.config[QUORUMS][committee_id]:
                    host = f"{neighbor[API_IP]}:{neighbor[PORT]}"
                    requests.post(f"http://{host}/remove+host", json={"remove_host": f"{request.host}"})

            del app.config[PBFT_INSTANCES]
            app.config[PBFT_INSTANCES] = None
            app.config[QUORUMS] = {}
            requests.get(f"http://{request.host}/start/{req['req_id_a']}/{req['req_id_b']}")
            join_a_json = {
                NEIGHBOURS: req['neighbors_a']
            }
            join_b_json = {
                NEIGHBOURS: req['neighbors_b']
            }
            requests.post(f"http://{request.host}/add/{req['req_id_a']}", json=join_a_json)
            requests.post(f"http://{request.host}/add/{req['req_id_b']}", json=join_b_json)

            app.logger.info(f"At the end of change+quorums: {app.config[QUORUMS]}")

            return ROUTE_EXECUTED_CORRECTLY
        else:
            return ROUTE_EXECUTION_FAILED.format(msg=f"Leaving would violate {id_a}-{id_b}'s integrity")

    # add neighbor from API when it joins
    @app.route('/add+host', methods=['POST'])
    def add_host():
        req = get_json(request, app)
        host = req["host"]
        host_quorum = req["host_quorum"]
        quorum = req["quorum"]
        docker_ip = req["docker_ip"]

        split_host = host.split(":")
        host_json = {
            API_IP: split_host[0],
            PORT: split_host[1],
            QUORUM_ID: host_quorum,
            DOCKER_IP: docker_ip
        }

        app.logger.info("Adding {q} to node {n}".format(q=host, n=app))

        app.config[QUORUMS][quorum].append(host_json)
            
        return ROUTE_EXECUTED_CORRECTLY

    # remove neighbor from API after it leaves
    @app.route('/remove+host', methods=['POST'])
    def remove_host():
        req = get_json(request, app)
        host = req["host"]

        app.logger.info("Removing {q} from node {n}".format(q=host, n=app))

        for committee_id in app.config[QUORUMS]:
            app.config[QUORUMS][committee_id] = [neighbor for neighbor in app.config[QUORUMS][committee_id] if (f"{neighbor[API_IP]}:{neighbor[PORT]}" != host)]
            
        return ROUTE_EXECUTED_CORRECTLY
    
    # add a validator to the quorum
    @app.route('/add+validator', methods=['POST'])
    def add_validator():
        req = get_json(request, app)
        quorum_id = req["quorum_id"]
        add_val_key = req["val_key"]
        intersection = app.config[PBFT_INSTANCES]
        if intersection.in_committee(quorum_id):
            val_keys = intersection.get_peers(quorum_id)
            val_keys.append(add_val_key)
            if intersection.update_committee(quorum_id, val_keys):
                return ROUTE_EXECUTED_CORRECTLY
            else:
                return ROUTE_EXECUTION_FAILED.format(msg="Committee update failed!")
        else:
            return ROUTE_EXECUTION_FAILED.format(msg=f"Peer not in quorum {quorum_id}")
    
    # remove a validator from the quorum
    @app.route('/remove+validator', methods=['POST'])
    def remove_validator():
        req = get_json(request, app)
        quorum_id = req["quorum_id"]
        remove_val_key = req["val_key"]
        intersection = app.config[PBFT_INSTANCES]
        if intersection.in_committee(quorum_id):
            val_keys = intersection.get_peers(quorum_id)
            val_keys.remove(remove_val_key)
            if intersection.update_committee(quorum_id, val_keys):
                return ROUTE_EXECUTED_CORRECTLY
            else:
                return ROUTE_EXECUTION_FAILED.format(msg="Committee update failed!")
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))
        

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

    @app.route('/val+keys/<quorum_id>')
    def val_keys(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return jsonify(app.config[PBFT_INSTANCES].get_peers(quorum_id))
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/ip/<quorum_id>')
    def ip(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return app.config[PBFT_INSTANCES].ip(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/ips/<quorum_id>')
    def ips(quorum_id):
        if app.config[PBFT_INSTANCES].in_committee(quorum_id):
            return jsonify(app.config[PBFT_INSTANCES].get_ips(quorum_id))
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))
