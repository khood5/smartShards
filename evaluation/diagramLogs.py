import sys
from datetime import datetime


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
    return int(timeDifference.total_seconds())


#Used in finding timing diagrams
if __name__ == '__main__':
    resultsSet = {}
    resultsLink = []
    for i in range(1, len(sys.argv), 1):
        linkLines = []
        #setFlag = False
        with open(sys.argv[i], "r") as f:
            fileList = list(f)
            prev = None
            for line in fileList:
                if line.find("intkey set") != -1:
                    txNumber = line[15:-1].split()[4]
                    resultsSet.update({txNumber: (line[0:8])})
                    #setFlag = True
                if prev is not None:
                    if prev.find("show") != -1 and line.find("999") != -1:
                        if resultsSet.get(prev[15:-1].split()[4]) is not None:
                            linkLines.append((resultsSet.get(prev[15:-1].split()[4]), prev[0:8]))
                prev = line
        resultsLink.append(linkLines)
    results = []
    #For each in resultsLink go through link lines with correct time
    #round = 0
    #For each log file
    for list in resultsLink:
        #For each tx in the log
        for tx in list:
            results.append(calculateTimeDiff(tx[0], tx[1]))
            #results.append(calculateTimeDiff(resultsSet[round], line))
        #round += 1
    resultsDict = {}
    for e in results:
        if e in resultsDict:
            resultsDict[e] += 1
        else:
            resultsDict[e] = 1
    with open("logOutput.csv", "w") as l:
        for key in sorted(resultsDict):
            l.write(str(key)+", "+str(resultsDict[key])+"\n")
