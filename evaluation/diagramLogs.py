from datetime import datetime
import re
from timingDiagramChurn import CHURN_RATES, EXPERIMENT_RANGE_END

experiments = EXPERIMENT_RANGE_END
churnRates = CHURN_RATES

logFormat = "logs/timingDiagramChurn.py.E{experiment}CR{churnRate}.SawtoothContainer.log"

submitted_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:running command: *intkey set (?P<tx_id>tx_\d+_\d+) (?P<tx_val>\d+)"
confirmed_format = "(?P<tx_time>\d+:\d+:\d+) INFO \d+.\d+.\d+.\d+:command result: *(?P<tx_id>tx_\d+_\d+): (?P<tx_val>\d+)"

#Takes two times, of format HH:MM:SS and finds the difference
def calculateTimeDiff(timeOne, timeTwo):
    postStripOne = datetime.strptime(timeOne, "%H:%M:%S")
    postStripTwo = datetime.strptime(timeTwo, "%H:%M:%S")
    if postStripOne.hour == 23 and postStripTwo.hour > 23:
        correctionPartOne = datetime(2021, 11, 25, 1)
        correctionPartTwo = datetime(2021, 11, 25, 13)
        correct = correctionPartOne - correctionPartTwo
        postStripOne.__add__(correct)
        postStripTwo.__add__(correct)
    timeDifference = postStripTwo - postStripOne
    return int(timeDifference.total_seconds()) % 86400


#Used in finding timing diagrams
if __name__ == '__main__':
    for churnRate in churnRates:
        resultsSet = {}
        resultsLink = []
        for experiment in range(experiments):
            linkLines = []
            #setFlag = False
            inputFilename = logFormat.format(experiment=experiment, churnRate=churnRate)
            print(f"opening {inputFilename}")
            with open(inputFilename, "r") as inputFile:
                logLines = list(inputFile)
                for line in logLines:

                    submit = re.search(submitted_format, line)
                    confirm = re.search(confirmed_format, line)

                    if submit is not None:
                        tx_id = submit.group('tx_id')
                        tx_val = submit.group('tx_val')
                        tx_time = submit.group('tx_time')
                        print("submit")
                        print(tx_id, tx_val, tx_time)
                        if tx_val == "999":
                            resultsSet.update({tx_id: (tx_time)})

                    if confirm is not None:
                        tx_id = confirm.group('tx_id')
                        tx_val = confirm.group('tx_val')
                        tx_time = confirm.group('tx_time')
                        print("confirm")
                        print(tx_id, tx_val, tx_time)
                        if tx_val == "999" and resultsSet.get(tx_id) is not None:
                            linkLines.append((resultsSet.get(tx_id), tx_time))

            resultsLink.append(linkLines)
        results = []
        #For each in resultsLink go through link lines with correct time
        #round = 0
        #For each log file
        for l in resultsLink:
            #For each tx in the log
            for tx in l:
                diff = calculateTimeDiff(tx[0], tx[1])
                if diff > 300:
                    print(tx)
                    print("diff:", diff)
                results.append(diff)
                #results.append(calculateTimeDiff(resultsSet[round], line))
            #round += 1
        resultsDict = {}
        for e in results:
            if e in resultsDict:
                resultsDict[e] += 1
            else:
                resultsDict[e] = 1
        outputFilename = f"latencyLogOutputCR{churnRate}.csv"
        print(f"writing {outputFilename}")
        with open(outputFilename, "w") as outputFile:
            outputFile.write(f"seconds,frequency\n")
            for seconds, frequency in sorted(resultsDict.items()):
                outputFile.write(f"{seconds},{frequency}\n")
