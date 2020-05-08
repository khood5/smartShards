import time
import argparse
from src.SawtoothPBFT import sawtooth_container_log_to, SawtoothContainer
from src.util import make_sawtooth_committee
from src.structures import Transaction
from src.Peer import peer_log_to
from src.Peer import Peer
from pathlib import Path

# defaults
NUMBER_OF_TX = 20
NUMBER_OF_EXPERIMENTS = 10
OUTPUT_FILE = "BasicIntersectionGraph.csv"


# Opens the output file and writes the results in it for each data point
def make_graph_data(outfile: str, experiments: int, total_tx: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Committee size, avg delay  (sec)\n")
    print("---------------------------------------------------------------------------------------")
    print("Starting experiments for committee size {}".format(4))
    avgs = get_avg_for(experiments, total_tx)
    print("Experiments for committee size {} ended".format(4))
    print("---------------------------------------------------------------------------------------")
    out.write("{s}, {c}\n".format(s=4, c=avgs["confirmed"]))
    out.close()


# runs each experiment and calc avgs (i.e. creates one data point)
# is responsible for creating and destroying peers
def get_avg_for(experiments: int, total_tx: int):
    confirmation_delays = []

    for e in range(experiments):
        print("Setting up experiment {}".format(e))
        peers = make_committees()
        results = run_experiment(peers, total_tx)
        confirmation_delays += results["delays"]
        print("Cleaning up experiment {}".format(e))
        del peers

    return {"confirmed": sum(confirmation_delays) / len(confirmation_delays), }


def make_committees():
    committee_a = make_sawtooth_committee(4)
    committee_b = make_sawtooth_committee(4)
    committee_c = make_sawtooth_committee(4)
    committee_d = make_sawtooth_committee(4)
    committee_e = make_sawtooth_committee(4)

    peer_1 = Peer(committee_a[0], committee_b[0], 'a', 'b')
    peer_2 = Peer(committee_a[1], committee_c[0], 'a', 'c')
    peer_3 = Peer(committee_a[2], committee_d[0], 'a', 'd')
    peer_4 = Peer(committee_a[3], committee_e[0], 'a', 'e')

    peer_5 = Peer(committee_b[1], committee_c[1], 'b', 'c')
    peer_6 = Peer(committee_b[2], committee_d[1], 'b', 'd')
    peer_7 = Peer(committee_b[3], committee_e[1], 'b', 'e')

    peer_8 = Peer(committee_c[2], committee_d[2], 'c', 'd')
    peer_9 = Peer(committee_c[3], committee_e[2], 'c', 'e')

    peer_10 = Peer(committee_d[3], committee_e[3], 'd', 'e')

    return [peer_1, peer_2, peer_3, peer_4, peer_5, peer_6, peer_7, peer_8, peer_9, peer_10]


def run_experiment(peers: list, total_tx: int):
    print("Running", end='', flush=True)
    confirmation_delays = []
    for i in range(total_tx):
        tx_1 = Transaction('a', 1)
        tx_name = 'test{}'.format(i)
        tx_1.key = tx_name
        tx_1.value = '999'
        peers[3].submit(tx_1)

        tx_2 = Transaction('b', 1)
        tx_name = 'test{}'.format(i)
        tx_2.key = tx_name
        tx_2.value = '999'
        peers[6].submit(tx_2)

        tx_3 = Transaction('c', 1)
        tx_name = 'test{}'.format(i)
        tx_3.key = tx_name
        tx_3.value = '999'
        peers[8].submit(tx_3)

        tx_4 = Transaction('d', 1)
        tx_name = 'test{}'.format(i)
        tx_4.key = tx_name
        tx_4.value = '999'
        peers[9].submit(tx_4)

        tx_5 = Transaction('e', 1)
        tx_name = 'test{}'.format(i)
        tx_5.key = tx_name
        tx_5.value = '999'
        peers[9].submit(tx_5)

        start_confirmed = time.time()

        confirmed = False
        while not confirmed:
            print('.', end='', flush=True)
            confirmed = True
            if peers[0].get_tx(tx_1) != '999':
                confirmed = False
            if peers[1].get_tx(tx_1) != '999':
                confirmed = False
            if peers[2].get_tx(tx_1) != '999':
                confirmed = False
            if peers[3].get_tx(tx_1) != '999':
                confirmed = False

            if peers[0].get_tx(tx_2) != '999':
                confirmed = False
            if peers[4].get_tx(tx_2) != '999':
                confirmed = False
            if peers[5].get_tx(tx_2) != '999':
                confirmed = False
            if peers[6].get_tx(tx_2) != '999':
                confirmed = False

            if peers[1].get_tx(tx_3) != '999':
                confirmed = False
            if peers[4].get_tx(tx_3) != '999':
                confirmed = False
            if peers[7].get_tx(tx_3) != '999':
                confirmed = False
            if peers[8].get_tx(tx_3) != '999':
                confirmed = False

            if peers[2].get_tx(tx_4) != '999':
                confirmed = False
            if peers[5].get_tx(tx_4) != '999':
                confirmed = False
            if peers[7].get_tx(tx_4) != '999':
                confirmed = False
            if peers[9].get_tx(tx_4) != '999':
                confirmed = False

            if peers[3].get_tx(tx_5) != '999':
                confirmed = False
            if peers[6].get_tx(tx_5) != '999':
                confirmed = False
            if peers[8].get_tx(tx_5) != '999':
                confirmed = False
            if peers[9].get_tx(tx_5) != '999':
                confirmed = False

        confirmation_delays.append(time.time() - start_confirmed)
    print()
    return {"delays": confirmation_delays}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a performance graph for Peer module. '
                                                 'Makes a basic set of intersecting committees (5 committees, '
                                                 '4 peers in each, committees intersect on one peer each)')
    parser.add_argument('-o', type=str,
                        help='File to output data (csv format)')
    parser.add_argument('-e', type=int,
                        help='Number of experiments to run per data point')
    parser.add_argument('-t', type=int,
                        help='Total number of transactions to submit')
    args = parser.parse_args()

    output_file = Path(args.o) if args.o is not None else Path().home().joinpath(OUTPUT_FILE)
    while not output_file.exists():
        output_file.touch()

    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    total_tx = NUMBER_OF_TX if args.t is None else args.t

    sawtooth_container_log_to(Path().home().joinpath('BasicIntersectionGraph.SawtoothContainer.log'))
    peer_log_to(Path().home().joinpath('BasicIntersectionGraph.Peer.log'))

    print("experiments:{e}, total_tx{t}".format(e=experiments, t=total_tx))

    make_graph_data(output_file, experiments, total_tx)
