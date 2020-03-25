from PBFT import PBFT


class Peer:
    instanceA = PBFT()
    instanceB = PBFT()
    instanceAid = -1
    instanceBid = -1
    id = '0'
    neighborsA = None
    neighborsB = None

    def __init__(self, quorumA, quorumB, Aid, Bid, id):
        self.instanceAid = Aid
        self.instanceBid = Bid
        self.id = id
        self.instanceA.start(quorumA)
        self.instanceB.start(quorumB)
        self.neighborsA = dict()
        self.neighborsB = dict()
        
    def addNeighbor(self, quorumid, NeighborsQuorum, NeighborId):
        if quorumid == self.instanceAid:
            self.neighborsA[NeighborId] = NeighborsQuorum
            return self.instanceBid

        elif quorumid == self.instanceBid:
            self.neighborsB[NeighborId] = NeighborsQuorum
            return self.instanceAid
            
        else:
            print("Error")

    def inserttransaction(self, tx):
        if tx.quorumid == self.instanceAid:
            self.instanceA.submit(tx)

        elif tx.quorumid == self.instanceBid:
            self.instanceB.submit(tx)
            
        elif tx.quorumid in self.neighborsA.values():
            neighbor = list(self.neighborsA.keys())[list(self.neighborsA.values()).index(tx.quorumid)]
            print("Route transaction")

        elif tx.quorumid in self.neighborsB.values():
            neighbor = list(self.neighborsB.keys())[list(self.neighborsB.values()).index(tx.quorumid)]
            print("Route transaction")
            
        else:
            print("Intersection Lost")