from src.structures import Transaction
from src.SawtoothPBFT import SawtoothContainer

class main:

    def __init__(self, n, intersections):
        self.quorums = dict()
        self.network = []
        size = int((n - 1) * n / 2)
        # These will all be needed but don't work for me
        # containers = [SawtoothContainer() for _ in range(size*intersections*2)]
        # user_keys = [i.user_key() for i in containers]
        # val_keys = [i.user_key() for i in containers]
        # committee_ips = [i.ip() for p in containers]
        containers = range(size*intersections*2)
        keyIndex = 0
        for _ in range (intersections):
            for i in range(n-1):
                offset = 1
                for _ in range((n-1)-i):
                    newEngineId = int(keyIndex/2)
                    newClusterEngine = ClusterEngine(i, offset + i, newEngineId, containers[keyIndex], containers[keyIndex + 1])
                    self.joinQuorums(newClusterEngine, i, offset + i)
                    self.addpeer(i, newEngineId)
                    self.addpeer(i + offset, newEngineId)
                    self.network.append(newClusterEngine)
                    offset = offset + 1
                    keyIndex += 2
    
    def addpeer(self, quorumid,  peerID):
        if quorumid in self.quorums:
            self.quorums[quorumid].append(peerID)
        else:
            self.quorums[quorumid] = list()
            self.quorums[quorumid].append(peerID)

    def joinQuorums(self, Engine, Aid, Bid):
        if Aid in self.quorums:
            for i in range(len(self.quorums[Aid])):
                NeighborsQuorum = self.network[self.quorums[Aid][i]].addNeighbor(Aid, Bid, Engine.id)
                Engine.addNeighbor(Aid, NeighborsQuorum, self.network[self.quorums[Aid][i]].id)

        if Bid in self.quorums:
            for i in range(len(self.quorums[Bid])):
                NeighborsQuorum = self.network[self.quorums[Bid][i]].addNeighbor(Bid, Aid, Engine.id)
                Engine.addNeighbor(Bid, NeighborsQuorum, self.network[self.quorums[Bid][i]].id)
