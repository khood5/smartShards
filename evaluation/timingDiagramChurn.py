import argparse
import gc
import socket
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
from random import random

POOLED = True

# Defaults
NUMBER_OF_TX = 20
NUMBER_OF_COMMITTEES = 5
INTERSECTION = 3
EXPERIMENT_RANGE_START = 0 
EXPERIMENT_RANGE_END = 20
EXPERIMENT_DURATION_SECS = 300
SAMPLE_MOD = 1

# Independent Variable
# CHURN_RATES = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
MACHINE_CHURN_RATES = {
    'jadamek3': [0.4],
    'jadamek7': [0.5],
    'jadamek8': [0.6],
    'jadamek9': [0.7],
    'jadamek10': [0.8],
    'jadamek11': [0.9],
    'jadamek12': [1],
}

hostname = socket.gethostname()

CHURN_RATES = MACHINE_CHURN_RATES[hostname]

# Const
IP_ADDRESS = "localhost"
URL_HOST = "http://{ip}:{port}"


# Run each experiment
def run_experiments(number_of_transactions: int, experiment_duration_secs: int, 
                    number_of_intersections: int, experiments_start: int, 
                    experiments_end: int, committees: int, churn_rate: float):
    
    for experiment_number in range(experiments_start, experiments_end):

        print(f"Setting up experiment {experiment_number} with churn rate {churn_rate}")
        log_format = f'{__file__}.E{experiment_number}CR{churn_rate}'
        sawtooth_log_handler = sawtooth_container_log_to(Path().cwd().joinpath('logs', f'{log_format}.SawtoothContainer.log'))
        intersection_log_handler = intersection_log_to(Path().cwd().joinpath('logs', f'{log_format}.Intersection.log'))
        smart_shard_peer_log_handler = smart_shard_peer_log_to(Path().cwd().joinpath('logs', f'{log_format}.SmartShardPeer.log'))
        peers = make_intersecting_committees_on_host(committees, number_of_intersections)

        print(f"Running experiment {experiment_number} with churn rate {churn_rate}")
        run_experiment(peers, experiment_duration_secs, number_of_transactions, churn_rate)
        
        print(f"Cleaning up experiment {experiment_number} with churn rate {churn_rate}")
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
def run_experiment(peers: dict, experiment_duration_secs: int, 
                   number_of_transactions: int, churn_rate: float):

    committee_ids_a = {peers[p].committee_id_a() for p in peers}
    committee_ids_b = {peers[p].committee_id_b() for p in peers}
    committee_ids = tuple(committee_ids_a.union(committee_ids_b))

    url_txs_by_round = []  # list of transactions that should be submitted per round
    
    # Creates the amount of groups of tx equal to the amount of runs
    for round in range(experiment_duration_secs):
        url_txs_by_round.append(create_txs(peers, committee_ids, number_of_transactions, round, churn_rate))
    
    startTime = time.time()
    endTime = startTime + experiment_duration_secs
    round = 0

    unconfirmed_transactions = []

    while (time.time() - startTime) < experiment_duration_secs:

        # Submit all of the transactions for the current round
        if POOLED:
            # Creates multiprocessing pool
            pool = ThreadPool(len(url_txs_by_round[round]))
            # Divides the task into the pool
            pool.map(submit_tx, url_txs_by_round[round])
            # Processes and rejoins the pool
            pool.close()
            pool.join()

            for url_tx in url_txs_by_round[round]:
                tx_id = int(url_tx[1].key.split('_')[2])
                take_sample = tx_id % SAMPLE_MOD == 0
                if take_sample:
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


def create_txs(peers, committee_ids, number_of_transactions, round, churn_rate):

    url_tx_tuples = []
    peer_ports = list(peers.keys())

    # Creates a group of transactions equal to the txNumber and the random number of churn transactions
    number_of_churn_transactions = 3 * sum( [ random() < churn_rate for _ in range(len(peer_ports)) ] )
    
    print(f"Creating {number_of_transactions} regular and {number_of_churn_transactions} churn transactions in round {round}")

    for tx_id in range(number_of_transactions + number_of_churn_transactions):
        is_churn = tx_id >= number_of_transactions
        tx_value = "777" if is_churn else "999"
        tx = Transaction(quorum=choice(committee_ids), key=f"tx_{round}_{tx_id}", value=tx_value)
        selected_peer = peer_ports[0]
        url = f"{URL_HOST.format(ip=IP_ADDRESS, port=selected_peer)}/submit/"
        url_tx_tuples.append((url, tx))
        peer_ports.append(peer_ports.pop(0))

    return url_tx_tuples


def submit_tx(url_tx):
    print(f"url_tx: {url_tx}")
    url, tx = url_tx
    print(f"Submitting ({tx.key}: {tx.value}) to {url}")
    requests.post(url, json=tx.to_json())


def update_confirmations(url_tx, confirmed_txs, port):

    get_url = f"{URL_HOST.format(ip=IP_ADDRESS, port=port)}/get/"

    submit_url, tx = url_tx

    print(f"Getting ({tx.key}: {tx.value}) from {get_url}")
    res = requests.post(get_url, json=tx.to_json())
    text = get_plain_text(res)
    print("------------------------------------")
    print(url_tx)
    print(confirmed_txs)
    print(f"The response's plaintext is: {text}")
    if tx.value == text:
        print("Confirmed!")
        confirmed_txs.append((submit_url, tx))


def update_url_txs(url_txs_by_round, peers, rounds, end_time):

    global confirmed_txs

    selected_peer = str(list(peers.keys())[0])
    get_url = f"{URL_HOST.format(ip=IP_ADDRESS, port=selected_peer)}/get/"

    for round_number in range(rounds):
        confirmed_txs = []

        for submit_url, tx in url_txs_by_round[round_number]:
            print(f"Getting ({tx.key}: {tx.value}) from {get_url}")
            res = requests.post(get_url, json=tx.to_json())
            text = get_plain_text(res)
            print(f"The response's plaintext is: {text}")
            if tx.value == text:
                print("Confirmed!")
                confirmed_txs.append((submit_url, tx))
            if time.time() >= end_time:
                break
        
        if time.time() >= end_time:
            break
        
        url_txs_by_round[round_number] = [url_tx for url_tx in url_txs_by_round[round_number] if url_tx not in confirmed_txs]



if __name__ == '__main__':
    for churn_rate in CHURN_RATES:        
        run_experiments(NUMBER_OF_TX, EXPERIMENT_DURATION_SECS, INTERSECTION, EXPERIMENT_RANGE_START, EXPERIMENT_RANGE_END,NUMBER_OF_COMMITTEES, churn_rate)
