from Peer import Peer
from transaction import transaction
from random import randint


class ClusterEngine:
    quorums = dict()  # key is quorum id and value is list of peers

    def __init__(self):
        self.quorums = dict()

    def addpeer(self, quorumid,  peer):
        if quorumid in self.quorums:
            self.quorums[quorumid].append(peer)
        else:
            self.quorums[quorumid] = list()
            self.quorums[quorumid].append(peer)

    # this must be ran once for each intersections
    # that is if clusters have 1 peer intersecting then run once
    # if they have 2 intersecting then run twice (with the same params)
    def addintersection(self, clusters):
        size = len(clusters)
        for i in range(size-1):
            cluster = clusters[i]
            offset = 1
            for j in range(len(cluster)-i):
                peer = Peer(cluster, clusters[offset], i, offset + i)
                self.addpeer(i, peer)
                self.addpeer(offset + i, peer)
                offset = offset + 1

    # sends transaction to random peer in correct quorum
    def inserttransaction(self, tx):
        num = randint(0, len(self.quorums[tx.quorumid]) - 1)
        peer = self.quorums[tx.quorumid][num]
        peer.inserttransaction(tx)

Cluster = ClusterEngine()
List = [['A1', 'B1'] , ['A2', 'C1'], ['B2', 'C2']]
Cluster.addintersection(List)


Cluster2 = ClusterEngine()
List2 = [['A1', 'B1', 'C1', 'D1'], ['A2', 'E1', 'F1', 'G1'], ['B2', 'E2', 'H1', 'I1'], ['C2', 'F2', 'H2', 'J1'], ['D2', 'G2', 'I2', 'J2']]
Cluster2.addintersection(List2)

t1 = transaction(0,0)
Cluster.inserttransaction(t1)
t2 = transaction(1,1)