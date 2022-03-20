import sys
from datetime import datetime

#Used in finding timing diagrams
if __name__ == '__main__':
    resultsSet = {}
    resultsLink = []
    for i in range(1, len(sys.argv), 1):
        linkLines = []
        totalTx = 0
        confirmedTx = 0
        print(f"opening {sys.argv[i]}")
        with open(sys.argv[i], "r") as f:
            fileList = list(f)
            for line, nextLine in zip(fileList[:-1], fileList[1:]):
                # If tx is submitted in the line
                if line.find("intkey set") != -1:
                    totalTx += 1
                if line.find("show") != -1 and nextLine.find("Error: No such key") == -1:
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
    with open("throughputLogOutputCR0.3.csv", "w") as l:
        l.write(f"experiment,submitted,confirmed\n")
        for experiment, (confirmed, submitted) in enumerate(resultsLink):
            l.write(f"{experiment},{submitted},{confirmed}\n")
        l.write(f"total,{totalTotalTx},{totalConfirmedTx}\n")
