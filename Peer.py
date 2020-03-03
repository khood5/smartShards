from PBFT import PBFT


class Peer:
    instanceA = PBFT()
    instanceB = PBFT()

    def __init__(self):
        self.instanceA = PBFT
        self.instanceB = PBFT

    def addto(self, quorumA, quorumB):
        self.instanceA.start(quorumA)
        self.instanceB.start(quorumB)



