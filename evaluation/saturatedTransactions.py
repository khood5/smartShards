import argparse
import gc
import time
from pathlib import Path
from random import choice

import requests
from src.Intersection import intersection_log_to
from src.SawtoothPBFT import sawtooth_container_log_to
from src.SmartShardPeer import smart_shard_peer_log_to
from src.api.api_util import get_plain_text
from src.structures import Transaction
from src.util import make_intersecting_committees_on_host

#Defaults
NUMBER_OF_TX_MULT = 3
NUMBER_OF_TX = 12
NUMBER_OF_COMMITTEES = 2
INTERSECTION = 7
NUMBER_OF_EXPERIMENTS = 3
OUTPUT_FILE = "TransactionSaturation.csv"

#Const
SUBTIME = 1
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


#Opens output file and writes results in it for each data point
def make_graph_data(outfile: str, max: int, number_of_intersections: int, experiments: int, committees: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    m = 1
    while m < NUMBER_OF_TX_MULT:
        out.write("Number of transactions submitted, throughput\n")
        print("----------------------------------------------------------")
        print("Starting experiments for transaction amount {}".format(max*m))
        avgs = get_avg_for((max*m), number_of_intersections, experiments, committees)
        print("Experiments for transaction amount {} ended".format(max*m))
        print("----------------------------------------------------------")
        out.write("{s}, {w}\n".format(s=(max*m), w=avgs["throughput"]))
        m += 1
    out.close()


#Run each experiment and calc avgs
def get_avg_for(number_of_transactions: int, number_of_intersections: int, experiments: int, committees: int):
    throughputPer5 = {}
    for e in range(experiments):
        print("Setting up experiment {}".format(e))
        peers = make_intersecting_committees_on_host(committees, number_of_intersections)
        results = run_experiment(peers, number_of_transactions)
        throughputPer5[e] = results["throughput"]
        print("Cleaning up experiment {}".format(e))
        del peers
        gc.collect()
    throughput = []
    for e in range(experiments):
        if len(throughputPer5[e]) == 0:
            throughputPer5[e] = 0
        else:
            throughputPer5[e] = sum(throughputPer5[e])/len(throughputPer5[e])
    for e in throughputPer5:
        throughput.append(throughputPer5[e])
    return {"throughput": sum(throughput) / len(throughput)}
    
#Gets the individual data for each amount of transactions sent
def run_experiment(peers: dict, number_of_transactions: int):
    print("Running", end='', flush=True)
    submitted_tx, amount_of_confirmedtx_per_5sec, confirmedTXs, urls = {}, [], [], []
    committee_ids = [peers[p].committee_id_a() for p in peers]
    committee_ids.extend([peers[p].committee_id_b() for p in peers])
    committee_ids = list(dict.fromkeys(committee_ids))
    peerList = list(peers.keys())
    peerQuorum = peersByQuorum(committee_ids, peers)
    m = 0
    while m < number_of_transactions:
        print("Submitting tx {}".format(m))
        tx = Transaction(quorum=choice(committee_ids), key="tx_{}".format(m), value="{}".format(999))
        m += 1
        submitted_tx[time.time()] = tx
        peerSelected = choice(peerList)
        url = URL_HOST.format(ip=IP_ADDRESS, port=peerSelected) + "/submit/"
        urls.append(url)
        #check_submitted_tx(confirmedTXs, submitted_tx, peerQuorum)
    for url in urls:
        requests.post(url, json=tx.to_json())
    #time.sleep(1)
    check_submitted_tx(confirmedTXs, submitted_tx, peerQuorum)
    amount_of_confirmedtx_per_5sec.append(len(confirmedTXs))
    #ensures that all submitted and confirmed transactions are added to list
    #if number_of_submitted_tx != 0 or len(confirmedTXs) != 0:
        #amount_of_submittedtx_per_5sec.append(number_of_submitted_tx)
        #number_of_submitted_tx = 0
        #amount_of_confirmedtx_per_5sec.append(len(confirmedTXs))
        #confirmedTXs.clear()
    throughputPer5 = []
    #Fix always displays 0 for first 5 seconds
    n = 0
    amountCommitted = 0
    #amountSubmitted = 0
    while n < len(amount_of_confirmedtx_per_5sec):
        amountCommitted += amount_of_confirmedtx_per_5sec[n]
        n += 1
    throughputPer5.append(float(amountCommitted/number_of_transactions))
    return {"throughput": throughputPer5}

def check_submitted_tx(confirmed, sub, port):
    remove_from_sub = []
    for tx in sub:
        url = URL_HOST.format(ip=IP_ADDRESS, port=choice(port[sub[tx].quorum_id]) + "/get/")
        if sub[tx].value == get_plain_text(requests.post(url, json=sub[tx].to_json())):
            confirmed.append(tx)
            remove_from_sub.append(tx)
    for r in remove_from_sub:
        del sub[r]

def peersByQuorum(quorum, peers):
    peerQuorum = {}
    for q in quorum:
        peerQuorum[q] = []
    for p in peers:
        peerQuorum[peers[p].committee_id_a()].append(str(peers[p].port))
        peerQuorum[peers[p].committee_id_b()].append(str(peers[p].port))
    return peerQuorum

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a performance graph for forward based on transaction amount. '
                                                 'Each data point is an amount of transactions. Runs from tx#=q to tx#=2p')
    parser.add_argument('-o', type=str, help='File to output data (csv format)')
    #parser.add_argument('-min', type=int, help='Starting number of transactions. Default {}'.format(NUMBER_OF_TX_MIN))
    parser.add_argument('-max', type=int, help='Max number of transactions. Default {}'.format(NUMBER_OF_TX))
    parser.add_argument('-i', type=int, help='Intersection between committees. Default {}'.format(INTERSECTION))
    parser.add_argument('-e', type=int, help='Number of experiments to run per data point. '
                                             'Default {}'.format(NUMBER_OF_EXPERIMENTS))
    parser.add_argument('-t', type=int, help='Total number of committees. Default {}'.format(NUMBER_OF_COMMITTEES))
    args = parser.parse_args()

    output_file = Path(args.o) if args.o is not None else Path().cwd().joinpath(OUTPUT_FILE)
    while not output_file.exists():
        output_file.touch()
    
    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    committees = NUMBER_OF_COMMITTEES if args.t is None else args.t
    #starting_number_of_transactions = NUMBER_OF_TX_MIN if args.min is None else args.min
    number_of_transactions = NUMBER_OF_TX if args.max is None else args.max
    number_of_intersections = INTERSECTION if args.i is None else args.i
    sawtooth_container_log_to(Path().cwd().joinpath('{}.SawtoothContainer.log'.format(__file__)))
    intersection_log_to(Path().cwd().joinpath('{}.Intersection.log'.format(__file__)))
    smart_shard_peer_log_to(Path().cwd().joinpath('{}.SmartShardPeer.log'.format(__file__)))
    print("experiments: {e}, committees: {c}".format(e=experiments, c=committees))

    make_graph_data(output_file, number_of_transactions, number_of_intersections, experiments, committees)
