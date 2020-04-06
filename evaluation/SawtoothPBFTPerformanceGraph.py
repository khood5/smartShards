import time
import argparse
from src.util import make_sawtooth_committee
from src.SawtoothPBFT import sawtooth_container_log_to
from pathlib import Path

# defaults
NUMBER_OF_TX = 10
NUMBER_OF_EXPERIMENTS = 5
MIN = 4
MAX = 8
OUTPUT_FILE = "SawtoothPBFTPerformanceGraph.csv"


# Opens the output file and writes the results in it for each data point
def make_graph_data(outfile: str, start_size: int, end_size: int, experiments: int, total_tx: int):
    out = open(outfile, 'w')
    print("Outputting to {}".format(outfile))
    out.write("Committee size, avg delay  (sec), avg propagation delay (sec)\n")

    for committee_size in range(start_size, end_size + 1):
        print("---------------------------------------------------------------------------------------")
        print("Starting experiments for committee size {}".format(committee_size))
        avgs = get_avg_for(committee_size, experiments, total_tx)
        print("Experiments for committee size {} ended".format(committee_size))
        print("---------------------------------------------------------------------------------------")
        out.write("{s}, {c}, {p}\n".format(s=committee_size, c=avgs["confirmed"], p=avgs["propagated"]))
    out.close()


# runs each experiment and calc avgs (i.e. creates one data point)
# is responsible for creating and destroying peers
def get_avg_for(size: int, experiments: int, total_tx: int):
    confirmation_delays = []
    propagation_delays = []

    for e in range(experiments):
        print("Setting up experiment {}".format(e))
        peers = make_sawtooth_committee(size)
        results = run_experiment(peers, total_tx)
        confirmation_delays += results["confirmation_delays"]
        propagation_delays += results["propagation_delays"]
        print("Cleaning up experiment {}".format(e))
        del peers

    return {"confirmed": sum(confirmation_delays) / len(confirmation_delays),
            "propagated": sum(propagation_delays) / len(propagation_delays)}


# this is one experiment func collects raw data
def run_experiment(peers: list, total_tx: int):
    print("Running", end='', flush=True)
    confirmation_delays = []
    propagated_delays = []
    for i in range(total_tx):
        tx_name = 'test{}'.format(i)
        peers[0].submit_tx(tx_name, '999')
        start_confirmed = time.time()
        start_propagated = time.time()

        propagated = False
        confirmed = False
        while not propagated:
            print('.', end='', flush=True)
            propagated = True
            for p in peers:
                if p.get_tx(tx_name) == '999' and not confirmed:
                    confirmation_delays.append(time.time() - start_confirmed)
                if p.get_tx(tx_name) != '999':
                    propagated = False

        propagated_delays.append(time.time() - start_propagated)
    print()
    return {"confirmation_delays": confirmation_delays,
            "propagation_delays": propagated_delays}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Make a performance graph for SawtoothPBFT module. '
                                                 'Each data point is a committee size. Runs from a min committee size '
                                                 'to a max')
    parser.add_argument('-o', type=str,
                        help='File to output data (csv format)')
    parser.add_argument('-min', type=int,
                        help='Starting . Default 4')
    parser.add_argument('-max', type=int,
                        help='Max committee size. Default 8')
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
    starting_size = MIN if args.min is None or args.min < 5 else args.min
    ending_size = MAX if args.max is None else args.max

    sawtooth_container_log_to(Path().home().joinpath('SawtoothContainer.log'))

    print("experiments:{e}, total_tx{t}".format(e=experiments, t=total_tx))

    make_graph_data(output_file, starting_size, ending_size, experiments, total_tx)
