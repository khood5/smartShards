import argparse
import gc
import json
import time
from math import floor
from pathlib import Path
from random import choice
from collections import deque
from multiprocessing import Pool as ThreadPool

import requests
from src.Intersection import intersection_log_to
from src.SawtoothPBFT import sawtooth_container_log_to
from src.SmartShardPeer import smart_shard_peer_log_to
from src.api.api_util import get_plain_text
from src.structures import Transaction
from src.util import make_intersecting_committees_on_host
from src.api.constants import QUORUM_ID, PORT

# Defaults
MAX_NUMBER_OF_TX = 21
MIN_NUMBER_OF_TX = 20
NUMBER_OF_COMMITTEES = 4
INTERSECTION = 3
NUMBER_OF_EXPERIMENTS = 1
OUTPUT_FILE = "TransactionSaturation.csv"
EXPERIMENT_DURATION_SECS = 120
MEASUREMENT_INTERVAL = 5

# Const
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


# Opens output file and writes results in it for each data point
def make_graph_data(outfile: Path, min: int, max: int, experiment_duration_secs: int, measurement_interval_secs: int,
                    number_of_intersections: int, experiments: int, committees: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    for number_of_tx in range(min, max):
        out.write("Number of transactions submitted, throughput\n")
        print("----------------------------------------------------------")
        print("Starting experiments for transaction amount {}".format(number_of_tx))
        avgs = get_avg_for(number_of_tx, experiment_duration_secs, measurement_interval_secs, number_of_intersections,
                           experiments, committees)
        print("Experiments for transaction amount {} ended".format(number_of_tx))
        print("----------------------------------------------------------")
        out.write("{s}, {w}\n".format(s=number_of_tx, w=avgs["throughput"]))
    out.close()


# Run each experiment and calc avgs
def get_avg_for(number_of_transactions: int, experiment_duration_secs: int, measurement_interval_secs: int,
                number_of_intersections: int, experiments: int, committees: int):
    throughputPer5 = {}
    for e in range(experiments):
        print("Setting up experiment {}".format(e))
        peers = make_intersecting_committees_on_host(committees, number_of_intersections)
        results = run_experiment(peers, experiment_duration_secs, measurement_interval_secs, number_of_transactions)
        throughputPer5[e] = results["throughput"]
        print("Cleaning up experiment {}".format(e))
        del peers
        gc.collect()
    throughput = []
    # For each experiment
    for e in range(experiments):
        # If no transactions were confirmed, inputs zero, to prevent dividing by zero
        if len(throughputPer5[e]) == 0:
            throughputPer5[e] = 0
        # takes the amount of transactions confirmed per experiment and divides them by the runs in each experiment
        else:
            throughputPer5[e] = sum(throughputPer5[e]) / len(throughputPer5[e])
    for e in throughputPer5:
        throughput.append(throughputPer5[e])
    return {"throughput": sum(throughput) / len(throughput)}


# Gets the individual data for each amount of transactions sent
# peers: dict of peers port number as key and SmartShardPeer as obj
# experiment_duration_secs: how long to run experiment for
# number_of_transactions: number of transactions per round (1 sec)
def run_experiment(peers: dict, experiment_duration_secs: int, measurement_interval_secs: int,
                   number_of_transactions: int):
    print("Running", end='', flush=True)
    committee_ids = [peers[p].committee_id_a() for p in peers]
    committee_ids.extend([peers[p].committee_id_b() for p in peers])
    committee_ids = list(dict.fromkeys(committee_ids))
    # peerList = list(peers.keys())
    peers_by_quorum = peersByQuorum(committee_ids, peers)
    unsubmitted_tx_by_round = []  # list of transactions that should be submitted per round
    # submittedTxList = []
    # peerQuorumList = peersByQuorumList(peers_by_quorum)

    # Creates the amount of groups of tx equal to the amount of runs
    for round in range(0, experiment_duration_secs):
        unsubmitted_tx_by_round.append(create_txs(peers, committee_ids, number_of_transactions, round))

    # # Creates a list of tuples of urls and json
    # # Use if on line 2
    # urlJsonList = []
    # for e in submittedTxList:
    #     urlJsonList.append(createUrlJsonList(e))
    # # Runs for the amount of runs

    # Grab start time Current minus start
    # if > seconds
    throughput = [0]
    round = 0
    startTime = time.time()
    while (time.time() - startTime) < experiment_duration_secs:
        round += 1
        # Creates multiprocessing pool
        pool = ThreadPool(number_of_transactions)
        # Divides the task into the pool
        pool.map(submit_tx, unsubmitted_tx_by_round[0])
        # Processes and rejoins the pool
        pool.close()
        pool.join()
        # Checks the transactions
        if floor(time.time() - startTime) % MEASUREMENT_INTERVAL == 0:
            total_confirmed = 0
            for quorum in peers_by_quorum:
                total_confirmed += check_submitted_tx(peers_by_quorum[quorum], quorum)
            throughput.append(total_confirmed - throughput[-1])

        # # Removes the top element from the groups of txs
        unsubmitted_tx_by_round.pop(0)
        # If less than 1 second has passed, sleep for the difference each round should be 1 sec
        if (time.time() - startTime) < round:
            experment_durration = time.time() - startTime
            round = floor(experment_durration)
            time.sleep(round - experment_durration)

    return {"throughput": throughput}


# peers: list of peers by port number
# quorums: quorum id
# and find the max size blockchain
def check_submitted_tx(peers: list, quorum: str):
    pool = ThreadPool(len(peers))
    results = pool.map(get_blockchain_len, [{PORT: p, QUORUM_ID: quorum} for p in peers])
    pool.close()
    pool.join()
    return max(results)


# peer: dict with a port and quorum id in the form {PORT: p, QUORUM_ID: quorum}
def get_blockchain_len(peer):
    url = URL_HOST.format(ip=IP_ADDRESS, port=peer[PORT]) + "/blocks/"
    size = len(json.loads(get_plain_text(requests.post(url,
                                                       json=json.loads(json.dumps(({QUORUM_ID: peer[QUORUM_ID]})))))))
    return size


# Creates a dictionary of quorums, which has the peer/ports of the quorum as values
def peersByQuorum(quorum, peers):
    peerQuorum = {}
    for q in quorum:
        peerQuorum[q] = []
    for p in peers:
        peerQuorum[peers[p].committee_id_a()].append(str(peers[p].port))
        peerQuorum[peers[p].committee_id_b()].append(str(peers[p].port))
    return peerQuorum


# Returns a list of each peer in a quorum. Each element corresponds to the quorum id
def peersByQuorumList(dict):
    peerQuorumList = []
    holdingList = []
    i = 0
    for k in dict:
        for v in dict[k]:
            holdingList.append(v)
        i = i + 1
        peerQuorumList.append(holdingList)
        holdingList.clear()
    return peerQuorumList


# Creates a grouping of tuples for the transactions. Time, tx, peer
# peers: list of peers by port number
# committee_ids: list of committee ids
# number_of_transactions: number of transactions to create
# round: the round number the tx should be submitted (in seconds into experiment )
# returns a list of urls and transactions to post to them
def create_txs(peers, committee_ids, number_of_transactions, round):
    url_tx_tuples = []
    peer_ports = list(peers.keys())
    # Creates a group of transactions equal to the txNumber
    for tx_id in range(0, number_of_transactions):
        tx = Transaction(quorum=choice(committee_ids), key="tx_{round}_{id}".format(round=round, id=tx_id), value="{}".format(999))
        selected_peer = peer_ports[0]
        url = URL_HOST.format(ip=IP_ADDRESS, port=selected_peer) + "/submit/"
        url_tx_tuples.append((url, tx))
        peer_ports.append(peer_ports.pop(0))
    return url_tx_tuples


# Submits each of the transactions, removes the used grouping from the list
# transactions: list of tuples in the form (url to submit tx to, the tx to submit)
def submit_tx(transactions):
    # Submits the transaction, using the url as a key
    requests.post(transactions[0], json=transactions[1].to_json())


def createUrlJsonList(sub):
    urlJsonList = []
    for tx in sub:
        url = URL_HOST.format(ip=IP_ADDRESS, port=tx[2] + "/get/")
        jsonTxt = tx[1].to_json()
        urlJsonList.append((url, jsonTxt))
    return urlJsonList


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a performance graph for forward based on transaction amount. '
                                                 'Each data point is an amount of transactions. Runs from tx#=q to tx#=2p')
    parser.add_argument('-o', type=str, help='File to output data (csv format)')
    parser.add_argument('-max', type=int,
                        help='Max number of transactions per round (1 sec). Default {}'.format(MAX_NUMBER_OF_TX))
    parser.add_argument('-min', type=int,
                        help='Min number of transactions per round (1 sec). Default {}'.format(MIN_NUMBER_OF_TX))
    parser.add_argument('-d', type=int, help='experiment duration in secs. Default {}'.format(EXPERIMENT_DURATION_SECS))
    parser.add_argument('-i', type=int, help='Intersection between committees. Default {}'.format(INTERSECTION))
    parser.add_argument('-e', type=int, help='Number of experiments to run per data point. '
                                             'Default {}'.format(NUMBER_OF_EXPERIMENTS))
    parser.add_argument('-t', type=int, help='Total number of committees. Default {}'.format(NUMBER_OF_COMMITTEES))
    parser.add_argument('-m', type=int, help='measurement interval in secs. Default {}'.format(MEASUREMENT_INTERVAL))
    args = parser.parse_args()

    output_file = Path(args.o) if args.o is not None else Path().cwd().joinpath(OUTPUT_FILE)
    while not output_file.exists():
        output_file.touch()

    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    committees = NUMBER_OF_COMMITTEES if args.t is None else args.t
    max_number_of_transactions = MAX_NUMBER_OF_TX if args.max is None else args.max
    min_number_of_transactions = MIN_NUMBER_OF_TX if args.min is None else args.min
    experiment_duration_secs = EXPERIMENT_DURATION_SECS if args.d is None else args.d
    measurement_interval_secs = MEASUREMENT_INTERVAL if args.m is None else args.m
    number_of_intersections = INTERSECTION if args.i is None else args.i
    sawtooth_container_log_to(Path().cwd().joinpath('{}.SawtoothContainer.log'.format(__file__)))
    intersection_log_to(Path().cwd().joinpath('{}.Intersection.log'.format(__file__)))
    smart_shard_peer_log_to(Path().cwd().joinpath('{}.SmartShardPeer.log'.format(__file__)))
    print("experiments: {e}, committees: {c}".format(e=experiments, c=committees))

    make_graph_data(output_file, min_number_of_transactions, max_number_of_transactions, experiment_duration_secs,
                    measurement_interval_secs, number_of_intersections, experiments, committees)
