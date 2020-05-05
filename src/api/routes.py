from src.api import APP, PBFT_PEER, SINGLE_PEER
from src.api import forms
from src.SawtoothPBFT import SawtoothContainer
from urllib.request import urlopen
from flask import render_template, jsonify, request
import json
import socket
import docker
import time

# keys for json values on various requests
JSON_KEYS = {
    'user': 'user_key',
    'val': 'validator_key',
    'ip': 'ip_address'
}

# default for new docker containers; not an overlay network local only
ACTIVE_PEERS = []


@APP.route('/')
@APP.route('/settings', methods=['GET', 'POST'])
def settings():
    add_form = forms.AddPeerForm()
    if add_form.validate_on_submit() and add_form.new_ip.data != "":
        new_peer = {'ip': add_form.new_ip.data, 'port': add_form.new_port.data}
        ACTIVE_PEERS.append(new_peer)

    rm_form = forms.RmPeerForm()
    if rm_form.validate_on_submit() and rm_form.old_ip.data != "":
        old_peer = {'ip': rm_form.old_ip.data, 'port': rm_form.old_port.data}
        for p in ACTIVE_PEERS:
            if p['ip'] == old_peer['ip'] and p['port'] == old_peer['port']:
                ACTIVE_PEERS.remove(p)
    return render_template('settings.html', title='Settings', add=add_form, rm=rm_form, peers=ACTIVE_PEERS)


# joins this peers dockers to a overlay swarm network
@APP.route('/docker/network/join', methods=['GET', 'POST'])
def docker_network_join():
    form = forms.OverlayJoinForm()
    # if form.validate_on_submit():
    #     network = form.name.data
    #     if SINGLE_PEER.attached_network() != network:
    #         del SINGLE_PEER


    return render_template('overlay_network.html', title='Network Settings', networkForm=form, peer=SINGLE_PEER)


# creates an overlay network managed by this node (in swarm)
@APP.route('/overlay/create')
def overlay_create():
    pass


# return info about the system flask is running on
@APP.route('/info')
def info():
    system_info = {'hostname': socket.gethostname(), 'ip_address': socket.gethostbyname(socket.gethostname())}
    client = docker.from_env()
    system_info.update(client.version())
    return jsonify(system_info)


# returns info about the peer
@APP.route('/peer')
def container_info():
    return jsonify(PBFT_PEER.info())


# request this a peer add (give permission) to another peer to committee a
@APP.route('/add/a', methods=['POST'])
def add_a():
    req = request.get_json(force=True)
    other_peers_user_key = req[JSON_KEYS['user_key']]
    other_peers_val_key = req[JSON_KEYS['val_key']]
    # my_peer add to a


# joins peers first instance (a) to a committee
@APP.route('/join/a', methods=['POST'])
def join_a():
    req = request.get_json(force=True)
    ips = req[JSON_KEYS['ip']]
    # my_peer join a


# request this a peer add (give permission) to another peer to committee a
@APP.route('/add/b', methods=['POST'])
def add_b():
    req = request.get_json(force=True)
    other_peers_user_key = req[JSON_KEYS['user_key']]
    other_peers_val_key = req[JSON_KEYS['val_key']]
    # my_peer add to b


# joins peers first instance (a) to a committee
@APP.route('/join/b', methods=['POST'])
def join_b():
    req = request.get_json(force=True)
    ips = req[JSON_KEYS['ip']]
    # my_peer join b


# request that this peer add another peer to committee
def make_genesis(json_req, committee):
    other_peers_user_key = json_req[JSON_KEYS['user_key']]
    other_peers_val_key = json_req[JSON_KEYS['val_key']]
    if committee == 'a':
        # add to a
        pass
    else:
        # add to b
        pass


###########################################################
# single methods to test functionality with single sawtooth

# single instance info
@APP.route('/info/s')
def s_info():
    single_peer_info = {JSON_KEYS['ip']: SINGLE_PEER.ip(),
                        JSON_KEYS['user']: SINGLE_PEER.usr_key(),
                        JSON_KEYS['val']: SINGLE_PEER.val_key()}
    return jsonify(single_peer_info)


# single instance join
@APP.route('/join/s')
def join_s():
    ips = []
    for peer in ACTIVE_PEERS:
        url = "http://{ip}:{peers_port}/s/info/".format(ip=peer['ip'], peers_port=peer['port'])
        data = json.loads(urlopen(url).read())
        ips.append(data['ip_address'])
    SINGLE_PEER.join_sawtooth(ips)

    return 'Called join_sawtooth with {}'.format(ips)


# single instance make gen
@APP.route('/genesis/s')
def make_genesis_s():
    other_peers_user_key = []
    other_peers_val_key = []
    for peer in ACTIVE_PEERS:
        url = "http://{ip}:{peers_port}/s/info/".format(ip=peer['ip'], peers_port=peer['port'])
        data = json.loads(urlopen(url).read())
        other_peers_val_key.append(data[JSON_KEYS['val']])
        other_peers_user_key.append(data[JSON_KEYS['user']])

    SINGLE_PEER.make_genesis(other_peers_val_key, other_peers_user_key)

    return 'Called make_genesis with \n' \
           'Val: {v}, \n' \
           'User: {u}'.format(v=other_peers_val_key, u=other_peers_user_key)


# submit tx
@APP.route('/submit/s')
def s_submit():
    key = 'test_{}'.format(round(time.time()))
    value = '999'
    SINGLE_PEER.submit_tx(key, value)
    return 'submitted tx key:{k}, value:{v}'.format(k=key, v=value)


# get tx
@APP.route('/gettx/s/<key>')
def gettx_s(key):
    value = SINGLE_PEER.get_tx(key)
    return 'get tx key:{k}, value:{v}'.format(k=key, v=value)


# get blocks
@APP.route('/blocks/s')
def blocks_s():
    return SINGLE_PEER.blocks()
