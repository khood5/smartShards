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
NUMBER_OF_COMMITTEES = 5
NUMBER_OF_INTERSECTIONS = 1
OUTPUT_FILE = "BasicIntersectionGraph.csv"


# Opens the output file and writes the results in it for each data point
def make_graph_data(outfile: str, experiments: int, total_tx: int, committeees: int, intersections: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Committee size, avg delay  (sec)\n")
    print("---------------------------------------------------------------------------------------")
    print("Starting experiments for committee size {}".format(4))
    avgs = get_avg_for(experiments, total_tx, committeees, intersections)
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
        results = run_experiment(peers, total_tx, committeees)
        confirmation_delays += results["delays"]
        print("Cleaning up experiment {}".format(e))
        del peers

    return {"confirmed": sum(confirmation_delays) / len(confirmation_delays), }


def run_experiment(peers: list, total_tx: int, n: int):
    print("Running", end='', flush=True)
    confirmation_delays = []
    for i in range(total_tx):
        List = []
        for k in range(n):
            List.append(Transaction(k, 1))
            List[k].key = 'test{}'.format(i)
            List[k].value = '999'
            for j in range(len(peers)):
                if (peers[j].committee_id_a == k or peers[j].committee_id_b == k):
                    peers[j].submit(List[k])
                    break

        start_confirmed = time.time()

        confirmed = False
        while not confirmed:
            print('.', end='', flush=True)
            confirmed = True

            for k in range(n):
                for j in range(len(peers)):
                    if (peers[j].committee_id_a == k or peers[j].committee_id_b == k):
                        if (peers[j].get_tx(List[k]) != '999'):
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
    parser.add_argument('-n', type=int,
                        help='Total number of committees')
    parser.add_argument('-i', type=int,
                        help='Total number of committee intersections')
    args = parser.parse_args()

    output_file = Path(args.o) if args.o is not None else Path().home().joinpath(OUTPUT_FILE)
    while not output_file.exists():
        output_file.touch()

    experiments = NUMBER_OF_EXPERIMENTS if args.e is None else args.e
    total_tx = NUMBER_OF_TX if args.t is None else args.t
    committeees = NUMBER_OF_COMMITTEES if args.n is None else args.n
    intersections = NUMBER_OF_INTERSECTIONS if args.i is None else args.i

    sawtooth_container_log_to(Path().home().joinpath('BasicIntersectionGraph.SawtoothContainer.log'))
    peer_log_to(Path().home().joinpath('BasicIntersectionGraph.Peer.log'))

    print("experiments:{e}, total_tx{t}".format(e=experiments, t=total_tx))

    make_graph_data(output_file, experiments, total_tx, committeees, intersections)
