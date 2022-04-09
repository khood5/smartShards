import re
from timingDiagramChurn import CHURN_RATES, EXPERIMENT_RANGE_END, SAMPLE_MOD

experiments = EXPERIMENT_RANGE_END
churnRates = CHURN_RATES

logFormat = "logs/timingDiagramChurn.py.E{experiment}CR{churnRate}.SawtoothContainer.log"

submitted_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:running command: *intkey set (?P<tx_key>tx_(?P<tx_round>\d+)_(?P<tx_id>\d+)) (?P<tx_val>\d+)"
confirmed_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:command result: *(?P<tx_key>tx_(?P<tx_round>\d+)_(?P<tx_id>\d+)): (?P<tx_val>\d+)"

#Used in finding timing diagrams
if __name__ == '__main__':
    for churnRate in churnRates:
        resultsSet = {}
        resultsLink = []
        for experiment in range(experiments):
            linkLines = []
            totalTx = 0
            confirmedTx = 0
            inputFilename = logFormat.format(experiment=experiment, churnRate=churnRate)
            print(f"opening {inputFilename}")
            with open(inputFilename, "r") as inputFile:
                logLines = list(inputFile)
                for line in logLines:

                    submit = re.search(submitted_format, line)
                    confirm = re.search(confirmed_format, line)
                    # If tx is submitted in the line
                    if submit is not None:
                        tx_key = submit.group('tx_key')
                        tx_round = int(submit.group('tx_round'))
                        tx_id = int(submit.group('tx_id'))
                        tx_val = int(submit.group('tx_val'))
                        tx_time = submit.group('tx_time')
                        if tx_val == 999 and tx_id % SAMPLE_MOD == 0:
                            print("submit")
                            print(tx_id, tx_val, tx_time)
                            totalTx += 1
                        
                    if confirm is not None:
                        tx_key = confirm.group('tx_key')
                        tx_round = int(confirm.group('tx_round'))
                        tx_id = int(confirm.group('tx_id'))
                        tx_val = int(confirm.group('tx_val'))
                        tx_time = confirm.group('tx_time')
                        if tx_val == 999 and tx_id % SAMPLE_MOD == 0:
                            print("confirm")
                            print(tx_id, tx_val, tx_time)
                            confirmedTx += 1
            resultsLink.append((confirmedTx, totalTx))
        results = []
        totalTotalTx = 0
        totalConfirmedTx = 0
        #For each in resultsLink go through link lines with correct time
        #For each log file
        resultsDict = {}
        for e in resultsLink:
            totalConfirmedTx += e[0]
            totalTotalTx += e[1]
        outputFilename = f"throughputLogOutputCR{churnRate}.csv"
        print(f"writing {outputFilename}")
        with open(outputFilename, "w") as outputFile:
            outputFile.write(f"experiment,submitted,confirmed\n")
            for experiment, (confirmed, submitted) in enumerate(resultsLink):
                outputFile.write(f"{experiment},{submitted},{confirmed}\n")
            outputFile.write(f"total,{totalTotalTx},{totalConfirmedTx}\n")
