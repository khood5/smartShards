from src.api import forms
from src.SawtoothPBFT import SawtoothContainer
from src.Peer import Peer
from urllib.request import urlopen
from flask import render_template, jsonify, request
import json
import socket
import docker
import time

# keys for json values on various requests
USER_KEY = 'user_key'
VALIDATOR_KEY = 'validator_key'
IP_ADDRESS = 'ip_address'
PORT = 'port'
NEIGHBOURS = 'neighbours'
SECRET = 'SECRET_KEY'
PEER = 'pbft'
DOCKER_NETWORK = 'network'
QUORUM_ID = 'quorum_id'
QUORUMS = 'quorums'
ROUTE_EXECUTED_CORRECTLY = "SUCCESS!"
ROUTE_EXECUTION_FAILED = "ERROR: {msg}"


def add_routes(app):
    @app.route('/', methods=['GET', 'POST'])
    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        peer_form = forms.PeerForm()
        if peer_form.validate_on_submit():
            print(peer_form.add_submit)
        return render_template('settings.html', title='Settings', peer=peer_form, peers=app.config[NEIGHBOURS])

    # joins this peers dockers to a overlay swarm network
    @app.route('/docker/network/join', methods=['GET', 'POST'])
    def docker_network_join():
        form = forms.OverlayJoinForm()
        # if form.validate_on_submit():
        #     network = form.name.data
        #     if SINGLE_PEER.attached_network() != network:
        #         del SINGLE_PEER

        return render_template('overlay_network.html',
                               title='Network Settings',
                               networkForm=form,
                               peer=app.get(PEER))

    # creates an overlay network managed by this node (in swarm)
    @app.route('/overlay/create')
    def overlay_create():
        pass

    # return info about the system flask is running on
    @app.route('/info')
    def info():
        system_info = {'hostname': socket.gethostname(), 'ip_address': socket.gethostbyname(socket.gethostname())}
        client = docker.from_env()
        system_info.update(client.version())
        return jsonify(system_info)

    # stat sawtooth for qurorum id
    @app.route('/start/<quorum_id_a>/<quorum_id_b>')
    def start(quorum_id_a=None, quorum_id_b=None):
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
            if app.config[PEER].committee_id_a != quorum_id and app.config[PEER].committee_id_b != quorum_id:
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
            for quorum in app.config[QUORUMS]:
                print(quorum)
        return ROUTE_EXECUTED_CORRECTLY
