from PBFT import PBFT


class Peer:
    instanceA = PBFT()
    instanceB = PBFT()

    def __init__(self, quorumA, quorumB):
        self.instanceA.start(quorumA)
        self.instanceB.start(quorumB)



