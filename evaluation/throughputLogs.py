import re

# experiments = 5
# churnRates = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]

experiments = 2
churnRates = [0.1]

logFormat = "logs/timingDiagramChurn.py.E{experiment}CR{churnRate}.SawtoothContainer.log"

submitted_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:running command: *intkey set (?P<tx_id>tx_\d+_\d+) (?P<tx_val>\d+)"
confirmed_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:command result: *(?P<tx_id>tx_\d+_\d+): (?P<tx_val>\d+)"

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
                        tx_id = submit.group('tx_id')
                        tx_val = submit.group('tx_val')
                        tx_time = submit.group('tx_time')
                        print("submit")
                        print(tx_id, tx_val, tx_time)
                        if tx_val == "999":
                            totalTx += 1
                        
                    if confirm is not None:
                        tx_id = confirm.group('tx_id')
                        tx_val = confirm.group('tx_val')
                        tx_time = confirm.group('tx_time')
                        print("confirm")
                        print(tx_id, tx_val, tx_time)
                        if tx_val == "999":
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
