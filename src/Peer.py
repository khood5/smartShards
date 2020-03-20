from PBFT import PBFT


class Peer:
    instanceA = PBFT()
    instanceB = PBFT()
    instanceAid = -1
    instanceBid = -1

    def __init__(self, quorumA, quorumB, Aid, Bid):
        self.instanceA.start(quorumA)
        self.instanceB.start(quorumB)
        self.instanceAid = Aid
        self.instanceBid = Bid

    def inserttransaction(self, tx):
        if tx.quorumid == self.instanceAid:
            self.instanceA.submit(tx)

        elif tx.quorumid == self.instanceBid:
            self.instanceB.submit(tx)
            
        else:
            print("Route transaction")



