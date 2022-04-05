import argparse
import gc
import time
from math import floor
from pathlib import Path
from random import choice
from multiprocessing.pool import ThreadPool
from itertools import repeat

import requests
from src.Intersection import intersection_log_to, intersection_remove_log
from src.SawtoothPBFT import sawtooth_container_log_to, sawtooth_container_remove_log
from src.SmartShardPeer import smart_shard_peer_log_to, smart_shard_peer_remove_log
from src.api.api_util import get_plain_text
from src.structures import Transaction
from src.util import make_intersecting_committees_on_host, stop_all_containers



# Quorums and Intersections to use
# 3 -- 20  == 60
# 4 -- 10 == 60
# 5 -- 6 == 60
# 6 -- 4 == 60
# 7 -- 3 == 63
# 8 -- 2 == 56
# 11 -- 1 == 55
# 12 -- 1 == 66
# 3 -- 10 == 30 DONE
# 4 -- 5 == 30 DONE
# 5 -- 3 == 30 DONE
# 6 -- 2 == 30 DONE
# 8 -- 1 == 28 DONE


# Defaults
POOLED = True
NUMBER_OF_TX = 100
NUMBER_OF_COMMITTEES = 3
INTERSECTION = 9
EXPERIMENTS = 10
EXPERIMENT_DURATION_SECS = 1500
#MEASUREMENT_INTERVAL = 5

# Const
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


# Run each experiment
def run_experiments(number_of_transactions: int, experiment_duration_secs: int,
                    number_of_intersections: int, experiments: int, committees: int):
    for experiment_number in range(experiments):

        print(f"Setting up experiment {experiment_number} with {number_of_transactions} transactions per second, {committees} committees, and {number_of_intersections} number of intersections")
        log_format = f'{__file__}.E{experiment_number}C{committees}I{number_of_intersections}'
        sawtooth_log_handler = sawtooth_container_log_to(Path().cwd().joinpath('logs', f'{log_format}.SawtoothContainer.log'))
        intersection_log_handler = intersection_log_to(Path().cwd().joinpath('logs', f'{log_format}.Intersection.log'))
        smart_shard_peer_log_handler = smart_shard_peer_log_to(Path().cwd().joinpath('logs', f'{log_format}.SmartShardPeer.log'))
        peers = make_intersecting_committees_on_host(committees, number_of_intersections)

        print(f"Running experiment {experiment_number}")
        run_experiment(peers, experiment_duration_secs, number_of_transactions)
        sawtooth_container_remove_log(sawtooth_log_handler)
        intersection_remove_log(intersection_log_handler)
        smart_shard_peer_remove_log(smart_shard_peer_log_handler)
        stop_all_containers()
        del peers
        gc.collect()

# Gets the individual data for each amount of transactions sent
# peers: dict of peers port number as key and SmartShardPeer as obj
# experiment_duration_secs: how long to run experiment for
# number_of_transactions: number of transactions per round (1 sec)
def run_experiment(peers: dict, experiment_duration_secs: int, number_of_transactions: int):

    committee_ids_a = [peers[p].committee_id_a() for p in peers]
    committee_ids_b = [peers[p].committee_id_b() for p in peers]
    committee_ids = tuple(commitee_ids_a.union(committee_ids_b))

    url_txs_by_round = []  # list of transactions that should be submitted per round

    # Creates the amount of groups of tx equal to the amount of runs
    for round in range(experiment_duration_secs):
        unsubmitted_tx_by_round.append(create_txs(peers, committee_ids, number_of_transactions, round))

    round = 0
    startTime = time.time()
    endTime = startTime + experiment_duration_secs

    unconfirmed_transactions = []

    while (time.time() - startTime) < experiment_duration_secs:

        #Submit all of the transactions for the current round
        if POOLED:
            # Creates multiprocessing pool
            pool = ThreadPool(len(url_txs_by_round[round]))
            # Divides the task into the pool
            pool.map(submit_tx, url_txs_by_round[round])
            # Processes and rejoins the pool
            pool.close()
            pool.join()

            for url_tx in url_txs_by_round[round]:
                unconfirmed_transactions.append(url_tx)

            confirmed_txs = []
            # Creates multiprocessing pool
            pool = ThreadPool(len(unconfirmed_transactions))
            # Divides the task into the pool
            pool.starmap(update_confirmations, zip(unconfirmed_transactions, repeat(confirmed_txs), repeat(str(list(peers.keys())[0]))))
            # Processes and rejoins the pool
            pool.close()
            pool.join()

            unconfirmed_transactions = [url_tx for url_tx in unconfirmed_transactions if url_tx not in confirmed_txs]
        else:
            for url_tx in url_txs_by_round[round]:
                submit_tx(url_tx)
                if time.time() >= endTime:
                    break


            update_url_txs(url_txs_by_round, peers, round, endTime)

        # If less than 1 second has passed, sleep for the difference
        if (time.time() - startTime) < round:
            time.sleep(round - (time.time() - startTime))

        round += 1


def create_txs(peers, committee_ids, number_of_transactions, round):

    url_tx_tuples = []
    peer_ports = list(peers.keys())

    # Creates a group of transactions equal to the txNumber

    for tx_id in range(number_of_transactions):
        tx = Transaction(quorum=choice(committee_ids), key=f"tx_{round}_{tx_id}", value="999")
        selected_peer = choice(peer_ports)
        url = f"{URL_HOST.format(ip=IP_ADDRESS, port=selected_peer)}/submit/"
        url_tx_tuples.append((url, tx))

    return url_tx_tuples


# Submits each of the transactions, removes the used grouping from the list
def submitTxs(url_tx):
    # Submits the transaction, using the url as a key
    url, tx = url_tx
    requests.post(url, json=tx.to_json())

def update_confirmations(url_tx, confirmed_txs, port):

    get_url = f"{URL_HOST.format(ip=IP_ADDRESS, port=port)}/get/"

    submit_url, tx = url_tx

    print(f"Getting {tx.key} from {get_url}")
    res = requests.post(get_url, json=tx.to_json())
    text = get_plain_text(res)
    if tx.value == text:
        confirmed_txs.append((submit_url, tx))


def update_url_txs(url_txs_by_round, peers, rounds, end_time):

    global confirmed_txs

    selected_peer = str(list(peers.keys())[0])
    get_url = f"{URL_HOST.format(ip=IP_ADDRESS, port=selected_peer)}/get/"

    for round_number in range(rounds):
        confirmed_txs = []

        for submit_url, tx in url_txs_by_round[round_number]:
            print(f"Getting {tx.key} from {get_url}")
            text = get_plain_text(res)
            if tx.value == text:
                confirmed_txs.append((submit_url, txs))
            if time.time() >= end_time:
                break

        if time.time() >= end_time:
            break

        url_txs_by_round[round_number] = [url_tx for url_tx in url_txs_by_round[round_number] if url_tx not in confirmed_txs]

if __name__ == '__main__':
    run_experiments(NUMBER_OF_TX, EXPERIMENT_DURATION_SECS, INTERSECTION, EXPERIMENTS, NUMBER_OF_COMMITTEES)
