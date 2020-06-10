from src.api.constants import NEIGHBOURS, PEER, QUORUMS, ROUTE_EXECUTED_CORRECTLY, PORT, QUORUM_ID
from src.api.constants import ROUTE_EXECUTION_FAILED, IP_ADDRESS, VALIDATOR_KEY, USER_KEY
from src.SawtoothPBFT import SawtoothContainer
from src.Peer import Peer
from src.structures import Transaction
from src.util import forward
from flask import jsonify, request
import socket


def add_routes(app):
    # return info about the system flask is running on
    @app.route('/')
    @app.route('/info/')
    @app.route('/info/<quorum_id>')
    def info(quorum_id=None):
        ip = socket.gethostbyname(socket.gethostname())
        port = request.host.split(':')[1]
        if app.config[PEER] is not None:
            if app.config[PEER].in_committee(quorum_id):
                system_info = {IP_ADDRESS: ip, PORT: port, QUORUM_ID: quorum_id}
                return jsonify(system_info)

        system_info = {IP_ADDRESS: ip, PORT: port, QUORUM_ID: None}
        return jsonify(system_info)

    # stat sawtooth for quorum id
    @app.route('/start/<quorum_id_a>/<quorum_id_b>')
    def start(quorum_id_a=None, quorum_id_b=None):
        if app.config[PEER] is not None:
            app.logger.warning("peer has already started, restarting")
            del app.config[PEER]
        instance_a = SawtoothContainer()
        instance_b = SawtoothContainer()
        app.config[PEER] = Peer(instance_a, instance_b, quorum_id_a, quorum_id_b)
        app.config[QUORUMS][quorum_id_a] = []
        app.config[QUORUMS][quorum_id_b] = []
        return ROUTE_EXECUTED_CORRECTLY

    # joins peers first instance (a) to a committee
    @app.route('/join/<quorum_id>', methods=['POST'])
    def join(quorum_id=None):
        # try and parse json
        try:
            req = request.get_json(force=True)
            neighbours = req[NEIGHBOURS]
        except KeyError as e:
            app.logger.error(e)
            return ROUTE_EXECUTION_FAILED.format(msg=e)
        # try to access peer object (if peer is inaccessible then peer has not started)
        try:
            # check and make sure peer is in quorum
            if not app.config[PEER].in_committee(quorum_id):
                app.logger.error("Peer not in committee {} can not join PBFT".format(quorum_id))
                return ROUTE_EXECUTION_FAILED.format(msg="Peer not in committee {} can not join PBFT"
                                                     .format('quorum_id'))
        except AttributeError as e:
            app.logger.error("Peer not started request /start/<quorum_id_a>/<quorum_id_b> first")
            app.logger.error(e)
            return ROUTE_EXECUTION_FAILED.format(msg="") + "Peer not started request " \
                                                           "/start/<quorum_id_a>/<quorum_id_b> first \n\n\n{}".format(e)

        app.logger.info("Joining {q} with neighbours {n}".format(q=quorum_id, n=neighbours))
        app.config[QUORUMS][quorum_id] = neighbours
        ips = [n[IP_ADDRESS] for n in app.config[QUORUMS][quorum_id]]
        ips.append(app.config[PEER].ip(quorum_id))
        app.config[PEER].peer_join(quorum_id, ips)
        return ROUTE_EXECUTED_CORRECTLY

    # request that genesis be made
    @app.route('/make+genesis/<quorum_id>', methods=['POST'])
    def make_genesis(quorum_id=None):
        try:
            req = request.get_json(force=True)
        except KeyError as e:
            return ROUTE_EXECUTION_FAILED.format(msg=e)
        val_keys = req[VALIDATOR_KEY]
        usr_keys = req[USER_KEY]
        if quorum_id == app.config[PEER].committee_id_a:
            app.config[PEER].make_genesis(quorum_id, val_keys, usr_keys)
        elif quorum_id == app.config[PEER].committee_id_b:
            app.config[PEER].make_genesis(quorum_id, val_keys, usr_keys)
        else:
            forward(app, "/make+genesis/{id}".format(id=quorum_id), quorum_id, req)
        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/submit/', methods=['POST'])
    def submit():
        try:
            req = request.get_json(force=True)
        except KeyError as e:
            return ROUTE_EXECUTION_FAILED.format(msg=e)
        if app.config[PEER].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            app.config[PEER].submit(tx)
        else:
            forward(app, "/submit/", req[QUORUM_ID], req)

        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/get/', methods=['POST'])
    def get():
        try:
            req = request.get_json(force=True)
        except KeyError as e:
            return ROUTE_EXECUTION_FAILED.format(msg=e)

        if app.config[PEER].in_committee(req[QUORUM_ID]):
            tx = Transaction()
            tx.load_from_json(req)
            return app.config[PEER].get_tx(tx)
        else:
            forward(app, "/get/", req[QUORUM_ID], req)

        return ROUTE_EXECUTED_CORRECTLY

    @app.route('/user+key/<quorum_id>')
    def usr_key(quorum_id):
        if app.config[PEER].in_committee(quorum_id):
            return app.config[PEER].user_key(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/val+key/<quorum_id>')
    def val_key(quorum_id):
        if app.config[PEER].in_committee(quorum_id):
            return app.config[PEER].val_key(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))

    @app.route('/ip/<quorum_id>')
    def ip(quorum_id):
        if app.config[PEER].in_committee(quorum_id):
            return app.config[PEER].ip(quorum_id)
        else:
            return ROUTE_EXECUTION_FAILED.format(msg="peer not in quorum {}".format(quorum_id))
