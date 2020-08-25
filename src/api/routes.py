import json

from src.api.constants import NEIGHBOURS, PBFT_INSTANCES, QUORUMS, ROUTE_EXECUTED_CORRECTLY, PORT, QUORUM_ID
from src.api.constants import ROUTE_EXECUTION_FAILED, API_IP, API_PORT, VALIDATOR_KEY, USER_KEY, DOCKER_IP, PENDING_PEERS, REFRESH_TYPE, NETWORK_SIZE
from src.SawtoothPBFT import SawtoothContainer
from src.Intersection import Intersection
from src.structures import Transaction
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

def check_pending_assigned(app, check_quorum=None, new_quorum=None):
    if check_quorum == new_quorum:
        return False
    quorums = app.config[QUORUMS]
    #self.refresh_config(PENDING_PEERS, self.port)

    for committee_id in quorums:
        for neighbor in quorums[committee_id]:
            neighbor_ip = neighbor[API_IP]
            neighbor_port = neighbor[PORT]
            neighbor_quorum = neighbor[QUORUM_ID]

            url = "http://{address}:{port}/check_pending_assigned/{check_quorum}/{new_quorum}".format(address=neighbor_ip, port=neighbor_port, new_quorum=new_quorum, check_quorum=check_quorum)
            already_assigned = json.loads(requests.post(url, json={}).text)["assigned"]
            if already_assigned:
                print("IN CPAROUTE RETURN TRUE")
                return True
            print("IN CPAROUTE RETURN FALSE")
    return False

def get_pending_quorum(app, joining_port):
    pending_quorum = None

    if len(app.config[PENDING_PEERS]) == 0:
        print("case a")
        highest_quorum_num = 0
        highest_quorum_id = None

        for quorum in app.config[QUORUMS]:
            our_quorum_num = int(quorum)
            if our_quorum_num > highest_quorum_num:
                highest_quorum_num = our_quorum_num
                highest_quorum_id = quorum

            neighbors = app.config[QUORUMS][quorum]
            for neighbor in neighbors:
                found_quorum_id = neighbor[QUORUM_ID]
                found_quorum_num = int(found_quorum_id)
                if found_quorum_num > highest_quorum_num:
                    highest_quorum_num = found_quorum_num
                    highest_quorum_id = found_quorum_id

        id_a = app.config[PBFT_INSTANCES].committee_id_a
        id_b = app.config[PBFT_INSTANCES].committee_id_b

        highest_local_quorum = max(int(id_a), int(id_b))

        if highest_local_quorum > highest_quorum_num:
            highest_quorum_num = highest_local_quorum
            highest_quorum_id = chr(highest_quorum_num + 48)
            print("HIGHEST LOCAL FOUND")
            print(highest_quorum_num)
            print(highest_quorum_id)

        next_quorum_num = highest_quorum_num + 1  
        next_quorum_id = chr(next_quorum_num + 48)
        pending_quorum = next_quorum_id

        app.config[PENDING_PEERS][pending_quorum] = []
        app.config[NETWORK_SIZE] = next_quorum_num
    else:
        print("case b")
        pending = app.config[PENDING_PEERS]
        pending_quorum = list(pending.keys())[0]

    try:
        check = app.config[PENDING_PEERS][pending_quorum].index(joining_port)
        return False
    except ValueError:
        pass     

    app.config[PENDING_PEERS][pending_quorum].append(str(joining_port))

    print("running check")
    print(app.config[PENDING_PEERS][pending_quorum]) 
    print(str(pending_quorum))

    if len(app.config[PENDING_PEERS][pending_quorum]) >= int(pending_quorum):
        inter = app.config[PBFT_INSTANCES]
        instance_a = inter.instance_a
        instance_b = inter.instance_b
        id_a = inter.committee_id_a
        id_b = inter.committee_id_b
        our_port = app.config[API_PORT]

        for joining_peer in app.config[PENDING_PEERS][pending_quorum]:
            index = app.config[PENDING_PEERS][pending_quorum].index(joining_peer)
            print("NET SIZE " + str(app.config[NETWORK_SIZE]) + " index " + str(index) + " PQ " + str(pending_quorum))
            if check_pending_assigned(app, str(index), pending_quorum):
                print("WAS ALREADY FOUND - SKIPPING")
                continue

            print("[" + str(app.config[API_PORT]) + "] Peer on port " + str(joining_peer) + " will be member of quorums " + str(index) + ", " + str(pending_quorum))
            new_a = instance_a
            new_b = SawtoothContainer()
            new_inter = Intersection(new_a, new_b, id_a, pending_quorum)
            net_size = app.config[NETWORK_SIZE] + 1
            
            containers_a = [SawtoothContainer() for _ in range(net_size)]
            user_keys_a = [i.user_key() for i in containers_a]
            val_keys_a = [i.val_key() for i in containers_a]
            committee_ips_a = [i.ip() for i in containers_a]

            containers_b = [SawtoothContainer() for _ in range(net_size)]
            user_keys_b = [i.user_key() for i in containers_b]
            val_keys_b = [i.val_key() for i in containers_b]
            committee_ips_b = [i.ip() for i in containers_b]

            intersections = [Intersection(containers_a[i], containers_b[i], id_a, id_b) for i in range(net_size)]

            intersections[0].make_genesis(id_a, val_keys_a, user_keys_a)
            intersections[0].make_genesis(id_b, val_keys_b, user_keys_b)

            ip_a = new_a.ip()
            ip_b = new_b.ip()
            val_key_a = new_a.val_key()
            val_key_b = new_b.val_key()
            user_key_a = new_a.user_key()
            user_key_b = new_b.user_key()

            new_inter.make_genesis(pending_quorum, val_keys_a, user_keys_a)
            new_inter.make_genesis(pending_quorum, val_keys_b, user_keys_b)

            ips_a = [p.ip() for p in containers_a]
            for p in containers_a:
                p.join_sawtooth(ips_a)

            ips_b = [p.ip() for p in containers_b]
            for p in containers_b:
                p.join_sawtooth(ips_b)

            app.config[PBFT_INSTANCES] = new_inter
            app.config[PENDING_PEERS][pending_quorum][index] = None

        print("setting size from " + str(app.config[NETWORK_SIZE]) + " to " + str(app.config[NETWORK_SIZE] + 1))
        app.config[NETWORK_SIZE] += 1
        print("size is now " + str(app.config[NETWORK_SIZE]))

    return pending_quorum

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

    @app.route('/check_pending_assigned/<check_quorum>/<new_quorum>', methods=['POST'])
    def check_pending_endpoint(check_quorum=None, new_quorum=None):
        inter = app.config[PBFT_INSTANCES]
        id_a = inter.committee_id_a
        id_b = inter.committee_id_b
        print("[" + str(app.config[API_PORT]) + "] IN ENDPOINT")
        print("CQ: " + check_quorum + "\nNQ: " + new_quorum + "\nA: " + id_a + "\nB: " + id_b)

        result = False

        if (check_quorum == id_a and new_quorum == id_b) or (check_quorum == id_b and new_quorum == id_a):
            print('CPA - quorum already added')
            result = True
        else:
            print("CPA - quorum was not found")
        
        res_json = json.loads(json.dumps({
            "assigned": result
        }))
        return res_json

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
        refresh_config(PENDING_PEERS, app)
        print("[" + str(app.config[API_PORT]) + "] NPP received " + str(peer_port))
        print(app.config[PENDING_PEERS])
        pending_quorum = get_pending_quorum(app, peer_port)
        print(pending_quorum)

        res_json = json.loads(json.dumps({
            "notifcation": pending_quorum
        }))

        return res_json

    # SmartShardPeer Joins a network mid-operation
    @app.route('/join_queue/', methods=['POST'])
    def join_queue():
        refresh_config(PENDING_PEERS, app)
        req = get_json(request, app)
        joining_port = req[PORT]

        print("running join_queue with port " + str(joining_port))
        
        pending_quorum = get_pending_quorum(app, joining_port)
        
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

    def refresh_config(type=None, app=None):
        if app.config[type]:
            res_json = json.loads(json.dumps({
                type: app.config[type]
            }))
            return res_json
        else:
            return ROUTE_EXECUTION_FAILED

    @app.route('/refresh_config/', methods=['POST'])
    def refresh_config_endpoint(type=None):
        req = get_json(request, app)
        type = req[REFRESH_TYPE]

        return refresh_config(type, app)

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
