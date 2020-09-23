import json

from src.api.constants import NEIGHBOURS, PBFT_INSTANCES, QUORUMS, ROUTE_EXECUTED_CORRECTLY, PORT, QUORUM_ID
from src.api.constants import ROUTE_EXECUTION_FAILED, API_IP, API_PORT, VALIDATOR_KEY, USER_KEY, DOCKER_IP, PENDING_PEERS, ACCEPTED_PEERS, REFRESH_TYPE, NETWORK_SIZE, TCP_IP, BOOTSTRAP
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.structures import Transaction
from src.util import refresh_config, get_pending_quorum, process_pending_quorums
from src.api.api_util import forward
from flask import jsonify, request
import requests
import socket

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
                system_info = {API_IP: ip, PORT: port, QUORUM_ID: quorum_id}
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

    @app.route('/check_pending_endpoint/<check_quorum>/<new_quorum>', methods=['POST'])
    def check_pending_endpoint(check_quorum=None, new_quorum=None):
        inter = app.config[PBFT_INSTANCES]
        id_a = inter.committee_id_a
        id_b = inter.committee_id_b
        print("[" + str(app.config[API_PORT]) + "] IN ENDPOINT")
        print("CQ: " + check_quorum + "\nNQ: " + new_quorum + "\nA: " + id_a + "\nB: " + id_b)

        result = False

        if (check_quorum == id_a and new_quorum == id_b) or (check_quorum == id_b and new_quorum == id_a) or (inter.instance_a.catching_up) or (inter.instance_b.catching_up):
            print('CPE - quorum already added')
            result = True
        else:
            print("CPE - quorum was not found")
        
        res_json = json.loads(json.dumps({
            "assigned": result
        }))
        return res_json

    @app.route('/spin_up_intersection/', methods=['POST'])
    def spin_up_intersection():
        req = get_json(request, app)
        id_a = req["id_a"]
        val_keys_a = []
        user_keys_a = []
        tcp_ips_a = []
        id_b = req["id_b"]
        val_keys_b = []
        user_keys_b = []
        tcp_ips_b = []

        neighbors = req["neighbors"]
        genesis = req["genesis"]

        for quorum in neighbors:
            for neighbor in neighbors[quorum]:
                val_key = neighbor[VALIDATOR_KEY]
                user_key = neighbor[USER_KEY]
                tcp_ip = neighbor[TCP_IP]

                val_keys_a.append(val_key)
                user_keys_a.append(user_key)
                tcp_ips_a.append(tcp_ip)

        app.config[QUORUMS] = neighbors

        new_a = SawtoothContainer()
        new_b = SawtoothContainer()

        if genesis == True:
            new_a.make_genesis(val_keys_a, user_keys_a)
            new_b.make_genesis(val_keys_b, user_keys_b)

        new_a.start_sawtooth(tcp_ips_a)
        new_b.start_sawtooth(tcp_ips_b)

        app.config[PBFT_INSTANCES] = Intersection(new_a, new_b, id_a, id_b)

        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/new_live_peer/<port>/<check_quorum>/<new_quorum>', methods=['POST'])
    def new_live_peer(port=None, check_quorum=None, new_quorum=None):
        req = get_json(request, app)
        port = str(port)

        try:
            app.config[ACCEPTED_PEERS][new_quorum][check_quorum][port] = True
        except KeyError:
            try:
                app.config[ACCEPTED_PEERS][new_quorum][check_quorum] = {}
            except KeyError:
                try:
                    app.config[ACCEPTED_PEERS][new_quorum] = {}
                    app.config[ACCEPTED_PEERS][new_quorum][check_quorum] = {}
                except KeyError:
                    return ROUTE_EXECUTION_FAILED
        
        app.config[ACCEPTED_PEERS][new_quorum][check_quorum][port] = True

        print("NLP request executed for " + port)
        
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

    @app.route('/new_pending_peer/<peer_port>', methods=['POST'])
    def new_pending_peer(peer_port=None):
        print("[" + str(app.config[API_PORT]) + "] NPP received " + str(peer_port))
        print(app.config[PENDING_PEERS])
        pending_quorum, app.config = get_pending_quorum(app.config, peer_port)

        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b

        self_neighbor_info_a = {
            API_IP: "localhost",
            TCP_IP: app.config[PBFT_INSTANCES].ip(id_a),
            PORT:   app.config[API_PORT],
            QUORUM_ID: id_a,
            USER_KEY: app.config[PBFT_INSTANCES].user_key(id_a),
            VALIDATOR_KEY: app.config[PBFT_INSTANCES].val_key(id_a)
        }

        self_neighbor_info_b = {
            API_IP: "localhost",
            TCP_IP: app.config[PBFT_INSTANCES].ip(id_b),
            PORT: app.config[API_PORT],
            QUORUM_ID: id_b,
            USER_KEY: app.config[PBFT_INSTANCES].user_key(id_b),
            VALIDATOR_KEY: app.config[PBFT_INSTANCES].val_key(id_b)
        }

        app.config = process_pending_quorums(app.config, pending_quorum, peer_port, self_neighbor_info_a, self_neighbor_info_b)
        

        res_json = json.loads(json.dumps({
            "notifcation": pending_quorum
        }))

        return res_json

    # SmartShardPeer Joins a network mid-operation
    @app.route('/join_queue/', methods=['POST'])
    def join_queue():
        req = get_json(request, app)
        joining_port = req[PORT]

        print("running join_queue with port " + str(joining_port))
        
        pending_quorum, app.config = get_pending_quorum(app.config, joining_port)

        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b

        self_neighbor_info_a = {
            API_IP: "localhost",
            TCP_IP: app.config[PBFT_INSTANCES].ip(id_a),
            PORT:   app.config[API_PORT],
            QUORUM_ID: id_a,
            USER_KEY: app.config[PBFT_INSTANCES].user_key(id_a),
            VALIDATOR_KEY: app.config[PBFT_INSTANCES].val_key(id_a)
        }

        self_neighbor_info_b = {
            API_IP: "localhost",
            TCP_IP: app.config[PBFT_INSTANCES].ip(id_b),
            PORT: app.config[API_PORT],
            QUORUM_ID: id_b,
            USER_KEY: app.config[PBFT_INSTANCES].user_key(id_b),
            VALIDATOR_KEY: app.config[PBFT_INSTANCES].val_key(id_b)
        }

        app.config = process_pending_quorums(app.config, pending_quorum, joining_port, self_neighbor_info_a, self_neighbor_info_b)
        
        res_json = json.loads(json.dumps({
            "notifcation": pending_quorum
        }))

        return res_json

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

    @app.route('/refresh_config/<type>', methods=['POST'])
    def refresh_config_endpoint(type=None):
        req = get_json(request, app)
      
        #print("RCE called with type " + type)
        #print(app.config)

        return refresh_config(type, app.config)

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
