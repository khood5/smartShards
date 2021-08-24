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
NUMBER_OF_TX_MIN = 1
NUMBER_OF_TX_MAX = 2
NUMBER_OF_COMMITTEES = 2
INTERSECTION = 7
NUMBER_OF_EXPERIMENTS = 1
OUTPUT_FILE = "TransactionSaturation.csv"

#Const
SUBTIME = 1
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


#Opens output file and writes results in it for each data point
def make_graph_data(outfile: str, min: int, max: int, number_of_intersections: int, experiments: int, committees: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Number of transactions submitted, throughput\n")
    #For each number of transaction
    for number_of_transactions in range(NUMBER_OF_TX_MIN, NUMBER_OF_TX_MAX + 1):
        print("----------------------------------------------------------")
        print("Starting experiments for transaction amount {}".format(number_of_transactions))
        avgs = get_avg_for(number_of_transactions, number_of_intersections, experiments, committees)
        print("Experiments for transaction amount {} ended".format(number_of_transactions))
        print("----------------------------------------------------------")
        out.write("{s}, {w}\n".format(s=number_of_transactions, w=avgs["throughput"]))
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
    submitted_tx, totalSubmitted, amount_of_confirmedtx_per_5sec, amount_of_submittedtx_per_5sec, confirmedTXs, \
    number_of_submitted_tx  = {}, 0, [], [], [], 0
    startSubFlag = 0
    committee_ids = [peers[p].committee_id_a() for p in peers]
    committee_ids.extend([peers[p].committee_id_b() for p in peers])
    committee_ids = list(dict.fromkeys(committee_ids))
    peerList = list(peers.keys())
    peerQuorum = peersByQuorum(committee_ids, peers)
    #next_sub = time.time() + SUBTIME
    #While there are still transactions to be made
    while totalSubmitted < number_of_transactions:
        if 1:
            #To allow many submitted in a given time swapped to always true
            #time.time() > next_sub:
            #Gets localtime
            currentTime = time.localtime(time.time())
            #Every 10 seconds starts a new time slot and if submissions have started
            if currentTime.tm_sec % 10 == 0 and startSubFlag == 1:
                amount_of_submittedtx_per_5sec.append(number_of_submitted_tx)
                number_of_submitted_tx = 0
                amount_of_confirmedtx_per_5sec.append(len(confirmedTXs))
                confirmedTXs.clear()
            print("Submitting tx {}".format(totalSubmitted))
            tx = Transaction(quorum=choice(committee_ids), key="tx_{}".format(totalSubmitted), value="{}".format(999))
            number_of_submitted_tx += 1
            totalSubmitted += 1
            submitted_tx[time.time()] = tx
            peerSelected = choice(peerList)
            startSubFlag = 1
            #Forces the transaction to go to a different committee than the one selected
            #FIX KEYERROR for forced
            #KeyError eg. '4'. likely a problem with directly comparing committee ids and the quorum ids
            #while peers[peerSelected].committee_id_a() == tx.quorum_id or ...committee_id_b() == tx.quorum_id:
            #    peerSelected = choice(committee_ids)
            url = URL_HOST.format(ip=IP_ADDRESS, port=peerSelected) + "/submit/"
            requests.post(url, json=tx.to_json())
            #Every 30 seconds places a period in console
            if time.time() % 30:
                print(" .", end='', flush=True)
            check_submitted_tx(confirmedTXs, submitted_tx, peerQuorum)
    #ensures that all submitted and confirmed transactions are added to list
    if number_of_submitted_tx != 0 or len(confirmedTXs) != 0:
        amount_of_submittedtx_per_5sec.append(number_of_submitted_tx)
        number_of_submitted_tx = 0
        amount_of_confirmedtx_per_5sec.append(len(confirmedTXs))
        confirmedTXs.clear()
    print()
    throughputPer5 = []
    #Fix always displays 0 for first 5 seconds
    n = 0
    while n < len(amount_of_confirmedtx_per_5sec):
    #for n in range(0, len(amount_of_confirmedtx_per_5sec)):
        if amount_of_submittedtx_per_5sec[n] == 0:
            throughputPer5.append(0)
        else:
            throughputPer5.append(float(amount_of_confirmedtx_per_5sec[n]/amount_of_submittedtx_per_5sec[n]))
        n += 1
    return {"throughput": throughputPer5}

def check_submitted_tx(confirmed, sub, port):
    remove_from_sub = []
    for tx in sub:
        url = URL_HOST.format(ip=IP_ADDRESS, port=choice(port[sub[tx].quorum_id]) + "/get/")
        time.sleep(.1)
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
    parser.add_argument('-min', type=int, help='Starting number of transactions. Default {}'.format(NUMBER_OF_TX_MIN))
    parser.add_argument('-max', type=int, help='Max number of transactions. Default {}'.format(NUMBER_OF_TX_MAX))
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
    starting_number_of_transactions = NUMBER_OF_TX_MIN if args.min is None else args.min
    ending_number_of_transactions = NUMBER_OF_TX_MAX if args.max is None else args.max
    number_of_intersections = INTERSECTION if args.i is None else args.i
    sawtooth_container_log_to(Path().cwd().joinpath('{}.SawtoothContainer.log'.format(__file__)))
    intersection_log_to(Path().cwd().joinpath('{}.Intersection.log'.format(__file__)))
    smart_shard_peer_log_to(Path().cwd().joinpath('{}.SmartShardPeer.log'.format(__file__)))
    print("experiments: {e}, committees: {c}".format(e=experiments, c=committees))

    make_graph_data(output_file, starting_number_of_transactions, ending_number_of_transactions,
                    number_of_intersections, experiments, committees)
