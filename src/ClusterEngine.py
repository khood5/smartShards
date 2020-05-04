from Peer import Peer


class ClusterEngine:
    peer = None
    instanceAid = -1
    instanceBid = -1
    id = None
    neighborsA = dict()
    neighborsB = dict()

    def __init__(self, Aid, Bid, id, sawtoothcontainer1, sawtoothcontainer2):
        self.peer = Peer(sawtoothcontainer1, sawtoothcontainer2, Aid, Bid)

        self.instanceAid = Aid
        self.instanceBid = Bid
        self.id = id
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

    # sends transaction to random peer in correct quorum
    def inserttransaction(self, tx):
        if tx.quorumid == self.instanceAid or tx.quorumid == self.instanceBid:
            self.peer.submit(tx)
            return -1

        elif tx.quorumid == self.instanceBid:
            self.peer.submit(tx)
            return -1
            
        elif tx.quorumid in self.neighborsA.values():
            neighbor = list(self.neighborsA.keys())[list(self.neighborsA.values()).index(tx.quorumid)]
            return neighbor

        elif tx.quorumid in self.neighborsB.values():
            neighbor = list(self.neighborsB.keys())[list(self.neighborsB.values()).index(tx.quorumid)]
            return neighbor
            
        else:
            print("Intersection Lost")
        