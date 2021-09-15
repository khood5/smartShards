import argparse
import gc
import time
from math import pow
from pathlib import Path
from random import choice
from collections import deque
from multiprocessing.dummy import Pool as ThreadPool

import requests
from src.Intersection import intersection_log_to
from src.SawtoothPBFT import sawtooth_container_log_to
from src.SmartShardPeer import smart_shard_peer_log_to
from src.api.api_util import get_plain_text
from src.structures import Transaction
from src.util import make_intersecting_committees_on_host

# Defaults
NUMBER_OF_TX_MULT = 2
NUMBER_OF_TX = 8
NUMBER_OF_COMMITTEES = 2
INTERSECTION = 7
NUMBER_OF_EXPERIMENTS = 3
OUTPUT_FILE = "TransactionSaturation.csv"

# Const
SUBTIME = 1
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


# Opens output file and writes results in it for each data point
def make_graph_data(outfile: str, max: int, number_of_intersections: int, experiments: int, committees: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    m = 1
    while m < NUMBER_OF_TX_MULT:
        out.write("Number of transactions submitted, throughput\n")
        print("----------------------------------------------------------")
        print("Starting experiments for transaction amount {}".format(pow(max, m)))
        avgs = get_avg_for(int(pow(max, m)), number_of_intersections, experiments, committees)
        print("Experiments for transaction amount {} ended".format(pow(max, m)))
        print("----------------------------------------------------------")
        out.write("{s}, {w}\n".format(s=(pow(max, m)), w=avgs["throughput"]))
        m += 1
    out.close()


# Run each experiment and calc avgs
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
    # For each experiment
    for e in range(experiments):
        # If no transactions were confirmed, inputs zero, to prevent dividing by zero
        if len(throughputPer5[e]) == 0:
            throughputPer5[e] = 0
        # takes the amount of transactions confirmed per experiment and divides them by the runs in each experiment
        else:
            throughputPer5[e] = sum(throughputPer5[e])/len(throughputPer5[e])
    for e in throughputPer5:
        throughput.append(throughputPer5[e])
    return {"throughput": sum(throughput) / len(throughput)}


# Gets the individual data for each amount of transactions sent
def run_experiment(peers: dict, number_of_transactions: int):
    print("Running", end='', flush=True)
    submitted_tx, amount_of_confirmedtx_per_5sec, confirmedTXs = {}, [], []
    committee_ids = [peers[p].committee_id_a() for p in peers]
    committee_ids.extend([peers[p].committee_id_b() for p in peers])
    committee_ids = list(dict.fromkeys(committee_ids))
    peerList = list(peers.keys())
    peerQuorum = peersByQuorum(committee_ids, peers)
    urlTXTuplesList = []
    submittedTxList = []
    # peerQuorumList = peersByQuorumList(peerQuorum)
    m = 0
    # Amount of individual runs per experiment
    seconds = 30
    # Creates the amount of groups of tx equal to the amount of runs
    while m < seconds:
        createTXs(number_of_transactions, urlTXTuplesList, committee_ids, submittedTxList, peerList, peerQuorum)
        m += 1
    o = 0
    # Creates a list of tuples of urls and json
    # Use if on line 2
    urlJsonList = []
    for e in submittedTxList:
        urlJsonList.append(createUrlJsonList(e))
    # Runs for the amount of runs
    startTime = time.time()
    # Grab start time Current minus start
    # if > seconds
    while (time.time() - startTime) < seconds:
        o += 1
        # Creates multiprocessing pool
        pool = ThreadPool(number_of_transactions)
        # Divides the task into the pool
        pool.map(submitTxs, urlTXTuplesList[0])
        # Processes and rejoins the pool
        pool.close()
        pool.join()
        # Checks the transactions
        check_submitted_tx(confirmedTXs, submittedTxList[0], urlJsonList[0])
        # Removes top of urlJsonList
        urlJsonList.pop(0)
        # Removes the group of submitted txs
        submittedTxList.pop(0)
        # Removes the top element from the groups of txs
        urlTXTuplesList.pop(0)
        # If less than 1 second has passed, sleep for the difference
        if (time.time() - startTime) < o:
            time.sleep(o - (time.time() - startTime))
    amount_of_confirmedtx_per_5sec.append((len(confirmedTXs))/(seconds-len(urlTXTuplesList)))
    throughputPer5 = []
    n = 0
    amountCommitted = 0
    while n < len(amount_of_confirmedtx_per_5sec):
        amountCommitted += amount_of_confirmedtx_per_5sec[n]
        n += 1
    throughputPer5.append(float(amountCommitted/number_of_transactions))
    return {"throughput": throughputPer5}


def check_submitted_tx(confirmed, sub, urlJsonList):
    remove_from_sub = []
    txsText = []
    pool = ThreadPool(number_of_transactions)
    txsText.append(pool.map(getTxs, urlJsonList))
    pool.close()
    pool.join()
    i = 0
    for tx in sub:
        if tx[1].value == txsText[0][i]:
            confirmed.append(tx)
            remove_from_sub.append(tx)
        i = i + 1


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


# Round robin this
# Creates a grouping of tuples for the transactions. Time, tx, peer
def createTXs(txNumber, listOfTuples, committee_ids, submittedTxList, peerList, peerQuorumList):
    n = 0
    submittedTx = []
    urlTXTuples = []
    peerSelected = deque(peerList)
    # Creates a group of transactions equal to the txNumber
    while n < txNumber:
        tx = Transaction(quorum=choice(committee_ids), key="tx_{}".format(n), value="{}".format(999))
        selectedPeer = choice(peerQuorumList[tx.quorum_id])
        submittedTx.append((time.time(), tx, selectedPeer))
        url = URL_HOST.format(ip=IP_ADDRESS, port=peerSelected[0]) + "/submit/"
        urlTXTuples.append((url, tx))
        n += 1
        poppedPeer = peerSelected.popleft()
        peerSelected.append(poppedPeer)
    # Adds the txs to a list of groups
    listOfTuples.append(urlTXTuples)
    # Also adds the txs to a list of dictionaries of txs
    submittedTxList.append(submittedTx)


# Submits each of the transactions, removes the used grouping from the list
def submitTxs(tuplesList):
    # Submits the transaction, using the url as a key
    requests.post(tuplesList[0], json=tuplesList[1].to_json())


#Gets the transactions
def getTxs(urlJsonList):
    return get_plain_text(requests.post(urlJsonList[0], json=urlJsonList[1]))


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
    number_of_transactions = NUMBER_OF_TX if args.max is None else args.max
    number_of_intersections = INTERSECTION if args.i is None else args.i
    sawtooth_container_log_to(Path().cwd().joinpath('{}.SawtoothContainer.log'.format(__file__)))
    intersection_log_to(Path().cwd().joinpath('{}.Intersection.log'.format(__file__)))
    smart_shard_peer_log_to(Path().cwd().joinpath('{}.SmartShardPeer.log'.format(__file__)))
    print("experiments: {e}, committees: {c}".format(e=experiments, c=committees))

    make_graph_data(output_file, number_of_transactions, number_of_intersections, experiments, committees)
