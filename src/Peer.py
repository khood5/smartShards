import src.SawtoothPBFT

class Peer:
    instanceA = None
    instanceB = None

    def __init__(self):
        self.instanceA = None
        self.instanceB = None

    def addto(self, quorumA, quorumB):
        self.instanceA.start(quorumA)
        self.instanceB.start(quorumB)



