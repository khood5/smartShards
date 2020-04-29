from src.api import app, my_peer, singlePeer
from src.api.forms import AddPeerForm, RmPeerForm
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

active_peers = []


@app.route('/')
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    add_form = AddPeerForm()
    if add_form.validate_on_submit() and add_form.new_ip.data != "":
        new_peer = {'ip': add_form.new_ip.data, 'port': add_form.new_port.data}
        active_peers.append(new_peer)

    rm_form = RmPeerForm()
    if rm_form.validate_on_submit() and rm_form.old_ip.data != "":
        old_peer = {'ip': rm_form.old_ip.data, 'port': rm_form.old_port.data}
        for p in active_peers:
            if p['ip'] == old_peer['ip'] and p['port'] == old_peer['port']:
                active_peers.remove(p)
    return render_template('settings.html', title='Settings', add=add_form, rm=rm_form, peers=active_peers)


# return info about the system flask is running on
@app.route('/info')
def info():
    system_info = {'hostname': socket.gethostname(), 'ip_address': socket.gethostbyname(socket.gethostname())}
    client = docker.from_env()
    system_info.update(client.version())
    return jsonify(system_info)


# returns info about the peer
@app.route('/peer')
def container_info():
    return jsonify(my_peer.info())


# request this a peer add (give permission) to another peer to committee a
@app.route('/add/a', methods=['POST'])
def add_a():
    req = request.get_json(force=True)
    other_peers_user_key = req[JSON_KEYS['user_key']]
    other_peers_val_key = req[JSON_KEYS['val_key']]
    # my_peer add to a


# joins peers first instance (a) to a committee
@app.route('/join/a', methods=['POST'])
def join_a():
    req = request.get_json(force=True)
    ips = req[JSON_KEYS['ip']]
    # my_peer join a


# request this a peer add (give permission) to another peer to committee a
@app.route('/add/b', methods=['POST'])
def add_b():
    req = request.get_json(force=True)
    other_peers_user_key = req[JSON_KEYS['user_key']]
    other_peers_val_key = req[JSON_KEYS['val_key']]
    # my_peer add to b


# joins peers first instance (a) to a committee
@app.route('/join/b', methods=['POST'])
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
@app.route('/s/info/')
def s_info():
    single_peer_info = {JSON_KEYS['ip']: singlePeer.ip(),
                        JSON_KEYS['user']: singlePeer.user_key(),
                        JSON_KEYS['val']: singlePeer.val_key()}
    return jsonify(single_peer_info)


# single instance join
@app.route('/s/join/')
def join_s():
    ips = []
    for peer in active_peers:
        url = "http://{ip}:{peers_port}/s/info/".format(ip=peer['ip'], peers_port=peer['port'])
        data = json.loads(urlopen(url).read())
        ips.append(data['ip_address'])
    singlePeer.join_sawtooth(ips)

    return 'Called join_sawtooth with {}'.format(ips)


# single instance make gen
@app.route('/s/genesis/')
def make_genesis_s():
    other_peers_user_key = []
    other_peers_val_key = []
    for peer in active_peers:
        url = "http://{ip}:{peers_port}/s/info/".format(ip=peer['ip'], peers_port=peer['port'])
        data = json.loads(urlopen(url).read())
        other_peers_val_key.append(data[JSON_KEYS['val']])
        other_peers_user_key.append(data[JSON_KEYS['user']])

    singlePeer.make_genesis(other_peers_val_key, other_peers_user_key)

    return 'Called make_genesis with \n' \
           'Val: {v}, \n' \
           'User: {u}'.format(v=other_peers_val_key, u=other_peers_user_key)


# submit tx
@app.route('/s/submit')
def submit_s():
    key = 'test_{}'.format(round(time.time()))
    value = '999'
    singlePeer.submit_tx(key, value)
    return 'submitted tx key:{k}, value:{v}'.format(k=key, v=value)


# get tx
@app.route('/s/gettx/<key>')
def gettx_s(key):
    value = singlePeer.get_tx(key)
    return 'get tx key:{k}, value:{v}'.format(k=key, v=value)


# get blocks
@app.route('/s/blocks')
def blocks_s():
    return singlePeer.blocks()
