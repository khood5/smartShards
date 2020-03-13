from Peer import Peer
from transaction import transaction


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
        if size > 0:
            cluster = clusters[0]
            offset = 0
            while len(cluster) < size:
                offset = offset + 1
                peer = Peer(cluster, clusters[offset])
                self.addpeer(cluster, peer)
                self.addpeer(offset, peer)

            self.addintersection(clusters[1:])

Cluster = ClusterEngine()
List = [['A1', 'B1'] , ['A2', 'C1'], ['B2', 'C2']] 
Cluster.addintersection(List)
t1 = transaction(0,0)