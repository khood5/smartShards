from Peer import Peer
from random import randint


class ClusterEngine:
    peer = None
    instanceAid = -1
    instanceBid = -1
    id = '0'
    neighborsA = dict()
    neighborsB = dict()

    def __init__(self, Aid, Bid, id, sawtoothcontainer1, sawtoothcontainer2):
        self.peer = Peer(sawtoothcontainer1, sawtoothcontainer2)

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
        if tx.quorumid == self.instanceAid:
            self.peer.inserttransaction(tx)

        elif tx.quorumid == self.instanceBid:
            self.peer.inserttransaction(tx)
            
        elif tx.quorumid in self.neighborsA.values():
            neighbor = list(self.neighborsA.keys())[list(self.neighborsA.values()).index(tx.quorumid)]
            print("Route transaction")

        elif tx.quorumid in self.neighborsB.values():
            neighbor = list(self.neighborsB.keys())[list(self.neighborsB.values()).index(tx.quorumid)]
            print("Route transaction")
            
        else:
            print("Intersection Lost")
        