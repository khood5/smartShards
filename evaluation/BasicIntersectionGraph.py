import time
import argparse
from src.SawtoothPBFT import sawtooth_container_log_to, SawtoothContainer
from src.util import make_sawtooth_committee
from src.util import make_intersecting_committees
from src.structures import Transaction
from src.Peer import peer_log_to
from src.Peer import Peer
from pathlib import Path

# defaults
NUMBER_OF_TX = 20
NUMBER_OF_EXPERIMENTS = 10
NUMBER_OF_INTERSECTIONS = 1
MIN = 5
MAX = 5
OUTPUT_FILE = "BasicIntersectionGraph.csv"


# Opens the output file and writes the results in it for each data point
def make_graph_data(outfile: str, start_size: int, end_size: int, experiments: int, total_tx: int, intersections: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Committee size, avg delay  (sec)\n")
    for committee_size in range(start_size, end_size + 1):
        print("---------------------------------------------------------------------------------------")
        print("Starting experiments for committee size {}".format(4))
        avgs = get_avg_for(experiments, total_tx, committee_size, intersections)
        print("Experiments for committee size {} ended".format(4))
        print("---------------------------------------------------------------------------------------")
        out.write("{s}, {c}\n".format(s=4, c=avgs["confirmed"]))
    out.close()


# runs each experiment and calc avgs (i.e. creates one data point)
# is responsible for creating and destroying peers
def get_avg_for(experiments: int, total_tx: int, committeees: int, intersections: int):
    confirmation_delays = []

    for e in range(experiments):
        print("Setting up experiment {}".format(e))
        peers = make_intersecting_committees(committeees, intersections)
        results = run_experiment(peers, total_tx)
        confirmation_delays += results["delays"]
        print("Cleaning up experiment {}".format(e))
        del peers

    return {"confirmed": sum(confirmation_delays) / len(confirmation_delays), }


def run_experiment(peers: list, total_tx: int):
    print("Running", end='', flush=True)
    confirmation_delays = []
    committee_ids = []
    for p in peers:
        if p.committee_id_a not in committee_ids:
            committee_ids.append(p.committee_id_a)
        if p.committee_id_b not in committee_ids:
            committee_ids.append(p.committee_id_b)

    for i in range(total_tx):
        new_tx = []
        for id in committee_ids:
            tx = Transaction(id, 1)
            tx.key = 'test{}'.format(i)
            tx.value = '999'
            for peer_index in range(len(peers)):
                if peers[peer_index].committee_id_a == id or peers[peer_index].committee_id_b == id:
                    peers[peer_index].submit(tx)
                    new_tx.append(tx)
                    break

        start_confirmed = time.time()

        confirmed = False
        while not confirmed:
            print('.', end='', flush=True)
            confirmed = True

            for id in committee_ids:
                for peer_index in range(len(peers)):
                    if peers[peer_index].committee_id_a == id or \
                       peers[peer_index].committee_id_b == id:

                        if peers[peer_index].get_tx(new_tx[id]) != '999':
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
    parser.add_argument('-min', type=int,
                        help='Starting . Default 5')
    parser.add_argument('-max', type=int,
                        help='Max committee size. Default 5')
    parser.add_argument('-i', type=int,
                        help='Total number of committee intersections')
    args = parser.parse_args()

    output_file = Path(args.o) if args.o is not None else Path().home().joinpath(OUTPUT_FILE)
    while not output_file.exists():
        output_file.touch()

    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    total_tx = NUMBER_OF_TX if args.t is None else args.t
    intersections = NUMBER_OF_INTERSECTIONS if args.i is None else args.i
    starting_size = MIN if args.min is None or args.min < 5 else args.min
    ending_size = MAX if args.max is None else args.max

    sawtooth_container_log_to(Path().home().joinpath('BasicIntersectionGraph.SawtoothContainer.log'))
    peer_log_to(Path().home().joinpath('BasicIntersectionGraph.Peer.log'))

    print("experiments:{e}, total_tx{t}".format(e=experiments, t=total_tx))

    make_graph_data(output_file, starting_size, ending_size, experiments, total_tx, intersections)
