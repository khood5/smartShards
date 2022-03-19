import argparse
import gc
import time
from math import floor
from pathlib import Path
from random import choice
from multiprocessing import Pool as ThreadPool

import requests
from src.Intersection import intersection_log_to
from src.SawtoothPBFT import sawtooth_container_log_to
from src.SmartShardPeer import smart_shard_peer_log_to
from src.api.api_util import get_plain_text
from src.structures import Transaction
from src.util import make_intersecting_committees_on_host, stop_all_containers
from random import random

# Defaults
NUMBER_OF_TX = 20
NUMBER_OF_COMMITTEES = 5
INTERSECTION = 3
NUMBER_OF_EXPERIMENTS = 5
OUTPUT_FILE = "TimingDiagramChurnRate{cr}.csv"
EXPERIMENT_DURATION_SECS = 300
MEASUREMENT_INTERVAL = 5

# Independent Variable
CHURN_RATES = [0.01, 0.02, 0.05, 0.1, 0.2]

# Const
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"

# Opens output file and writes results in it for each data point
def make_graph_data(outfile: Path, number_of_tx: int, experiment_duration_secs: int, measurement_interval_secs: int,
                    number_of_intersections: int, experiments: int, committees: int, churn_rate: float):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Seconds for confirmation, Number of confirmed transactions\n")
    print("----------------------------------------------------------")
    print("Starting experiments for transaction amount {}".format(number_of_tx))
    avgs = get_avg_for(number_of_tx, experiment_duration_secs, measurement_interval_secs, number_of_intersections,
                           experiments, committees, churn_rate)
    print("Experiments for transaction amount {} ended".format(number_of_tx))
    print("----------------------------------------------------------")
    out.write("{s}, {w}\n".format(s=number_of_tx, w=avgs["throughput"]))
    out.close()


# Run each experiment and calc avgs
def get_avg_for(number_of_transactions: int, experiment_duration_secs: int, measurement_interval_secs: int,
                number_of_intersections: int, experiments: int, committees: int, churn_rate: float):
    throughputPerE = {}
    for e in range(experiments):
        print("Setting up experiment {} with churn rate {}".format(e, churn_rate))
        sawtooth_container_log_to(Path().cwd().joinpath('{}.E{}CR{}.SawtoothContainer.log'.format(__file__, e, churn_rate)))
        intersection_log_to(Path().cwd().joinpath('{}.E{}CR{}.Intersection.log'.format(__file__, e, churn_rate)))
        smart_shard_peer_log_to(Path().cwd().joinpath('{}.E{}CR{}.SmartShardPeer.log'.format(__file__, e, churn_rate)))
        peers = make_intersecting_committees_on_host(committees, number_of_intersections)
        print("Running experiment {} with churn rate {}".format(e, churn_rate))
        results = run_experiment(peers, experiment_duration_secs, measurement_interval_secs, number_of_transactions, churn_rate)
        throughputPerE[e] = results["throughput"]
        print("Cleaning up experiment {} with churn rate {}".format(e, churn_rate))
        stop_all_containers()
        del peers
        gc.collect()
    throughput = {}
    # For each experiment
    for e in range(experiments):
        # If no transactions were confirmed, inputs zero, to prevent dividing by zero
        if len(throughputPerE[e]) == 0:
            throughputPerE[e] = 0
        # takes the amount of transactions confirmed per experiment and divides them by the runs in each experiment
        else:
            for key in throughputPerE[e]:
                if key in throughput:
                    value = throughput[key] + throughputPerE[e][key]
                    throughput[key] = value
                else:
                    throughput[key] = throughputPerE[e][key]
    sortedlist = sorted(throughput.items())
    #key = lambda x: x[0]
    sortedThroughput = dict(sortedlist)
    return {"throughput": sortedThroughput}


# Gets the individual data for each amount of transactions sent
# peers: dict of peers port number as key and SmartShardPeer as obj
# experiment_duration_secs: how long to run experiment for
# number_of_transactions: number of transactions per round (1 sec)
def run_experiment(peers: dict, experiment_duration_secs: int, measurement_interval_secs: int,
                   number_of_transactions: int, churn_rate: float):
    print("Running", end='', flush=True)
    committee_ids = [peers[p].committee_id_a() for p in peers]
    committee_ids.extend([peers[p].committee_id_b() for p in peers])
    committee_ids = list(dict.fromkeys(committee_ids))
    peers_by_quorum = peersByQuorum(committee_ids, peers)
    unsubmitted_tx_by_round = []  # list of transactions that should be submitted per round
    txTimeSubAndConf = []
    # Creates the amount of groups of tx equal to the amount of runs
    for round in range(0, experiment_duration_secs):
        txTimeSubAndConf.append([])
        unsubmitted_tx_by_round.append(create_txs(peers, committee_ids, number_of_transactions, round, txTimeSubAndConf, churn_rate))
    round = 0
    startTime = time.time()
    lastTime = startTime
    while (time.time() - startTime) < experiment_duration_secs:
        # Creates multiprocessing pool
        #pool = ThreadPool(number_of_transactions)
        # Divides the task into the pool
        #pool.map(submitTxs, unsubmitted_tx_by_round[round])
        # Processes and rejoins the pool
        #pool.close()
        #pool.join()
        for tx in unsubmitted_tx_by_round[round]:
            submitTxs(tx)
        for tx in txTimeSubAndConf[round]:
            tx.append(floor(time.time()))
        if floor(time.time() - lastTime) > measurement_interval_secs:
            for totalRounds in range(0, round):
                check_from_peers(unsubmitted_tx_by_round[totalRounds], txTimeSubAndConf[totalRounds], peers)
            lastTime = floor(time.time())
        # If less than 1 second has passed, sleep for the difference
        if (time.time() - startTime) < round:
            time.sleep(round - (time.time() - startTime))
        round += 1
    for totalRounds in range(0, round):
        check_from_peers(unsubmitted_tx_by_round[totalRounds], txTimeSubAndConf[totalRounds], peers)
    timeToConfirm = {}
    for totalRounds in range(0, round):
        for tx in range(0, number_of_transactions):
            if len(txTimeSubAndConf[totalRounds][tx])>1:
                if (floor(txTimeSubAndConf[totalRounds][tx][1])-floor(txTimeSubAndConf[totalRounds][tx][0])) in timeToConfirm:
                    timeToConfirm[(floor(txTimeSubAndConf[totalRounds][tx][1])-floor(txTimeSubAndConf[totalRounds][tx][0]))] += 1
                else:
                    timeToConfirm[(floor(txTimeSubAndConf[totalRounds][tx][1]) - floor(txTimeSubAndConf[totalRounds][tx][0]))] = 1
    #throughput = []
    #for key in timeToConfirm:
        #throughput.append((key, timeToConfirm.get(key)))
    return {"throughput": timeToConfirm}


def check_from_peers(submitted, confirmed, peers):
    url = URL_HOST.format(ip=IP_ADDRESS, port=str(list(peers.keys())[0]) + "/get/")
    remove_from_sub = []
    #intersectionA = peers[list(peers.keys())[0]].inter
    #intersectionA.get_tx(tx[1]) ==
    for tx in submitted:
        if tx[1].value == get_plain_text(requests.post(url, json=tx[1].to_json())):
            remove_from_sub.append(tx)
            txID = (tx[1].key.split('_'))[2]
            confirmed[int(txID)].append(floor(time.time()))
    for r in remove_from_sub:
        i = 0
        for tx in submitted:
            if r[1].key == tx[1].key:
                del submitted[i]
                break
            i += 1


# Submits each of the transactions, removes the used grouping from the list
def submitTxs(tuplesList):
    # Submits the transaction, using the url as a key
    requests.post(tuplesList[0], json=tuplesList[1].to_json())


def setTime(txTime):
    txTime.append(floor(time.time()))


def create_txs(peers, committee_ids, number_of_transactions, round, txTimeSubAndConf, churn_rate):
    url_tx_tuples = []
    peer_ports = list(peers.keys())
    churn_transactions = 3 * sum( [ random() < churn_rate for _ in range(len(peer_ports)) ] )
    # Creates a group of transactions equal to the txNumber
    for tx_id in range(0, number_of_transactions + churn_transactions):
        tx = Transaction(quorum=choice(committee_ids), key="tx_{round}_{id}".format(round=round, id=tx_id), value="{}".format(999))
        selected_peer = peer_ports[0]
        url = URL_HOST.format(ip=IP_ADDRESS, port=selected_peer) + "/submit/"
        url_tx_tuples.append((url, tx, time.time()))
        peer_ports.append(peer_ports.pop(0))
        txTimeSubAndConf[round].append(([]))
    return url_tx_tuples


# Creates a dictionary of quorums, which has the peer/ports of the quorum as values
def peersByQuorum(quorum, peers):
    peerQuorum = {}
    for q in quorum:
        peerQuorum[q] = []
    for p in peers:
        peerQuorum[peers[p].committee_id_a()].append(str(peers[p].port))
        peerQuorum[peers[p].committee_id_b()].append(str(peers[p].port))
    return peerQuorum



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a performance graph based on throughput per measurement interval. '
                                                 'Each data point is an amount of transactions. Runs from tx#=q to tx#=2p')
    parser.add_argument('-o', type=str, help='File to output data (csv format)')
    parser.add_argument('-max', type=int,
                        help='Max number of transactions per round (1 sec). Default {}'.format(NUMBER_OF_TX))
    parser.add_argument('-d', type=int, help='experiment duration in secs. Default {}'.format(EXPERIMENT_DURATION_SECS))
    parser.add_argument('-i', type=int, help='Intersection between committees. Default {}'.format(INTERSECTION))
    parser.add_argument('-e', type=int, help='Number of experiments to run per data point. '
                                             'Default {}'.format(NUMBER_OF_EXPERIMENTS))
    parser.add_argument('-t', type=int, help='Total number of committees. Default {}'.format(NUMBER_OF_COMMITTEES))
    parser.add_argument('-m', type=int, help='measurement interval in secs. Default {}'.format(MEASUREMENT_INTERVAL))
    args = parser.parse_args()

    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    committees = NUMBER_OF_COMMITTEES if args.t is None else args.t
    number_of_transactions = NUMBER_OF_TX if args.max is None else args.max
    experiment_duration_secs = EXPERIMENT_DURATION_SECS if args.d is None else args.d
    measurement_interval_secs = MEASUREMENT_INTERVAL if args.m is None else args.m
    number_of_intersections = INTERSECTION if args.i is None else args.i

    for churn_rate in CHURN_RATES:
        output_file = Path(args.o) if args.o is not None else Path().cwd().joinpath(OUTPUT_FILE.format(cr=churn_rate))
        while not output_file.exists():
            output_file.touch()
        
        print("experiments: {e}, committees: {c}, churn rate: {cr}".format(e=experiments, c=committees, cr=churn_rate))

        make_graph_data(output_file, number_of_transactions, experiment_duration_secs,
                        measurement_interval_secs, number_of_intersections, experiments, committees, churn_rate)
