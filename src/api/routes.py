from src.api import forms
from src.SawtoothPBFT import SawtoothContainer
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
PBFT_INSTANCES = 'pbft'
DOCKER_NETWORK = 'network'
QUORUM_ID = 'quorum_id'


def add_routes(app):
    @app.route('/')
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
                               peer=app.get(PBFT_INSTANCES))

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

    # joins peers first instance (a) to a committee
    @app.route('/add_to/', methods=['POST'])
    def add_to():
        req = request.get_json(force=True)
        quorum = req[QUORUM_ID]


        # my_peer join a
