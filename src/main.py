from ClusterEngine import ClusterEngine
from structures import Transaction
import docker as dockerapi
from SawtoothPBFT import SawtoothContainer
from random import choice

class main:
    quorums = None
    network = None
    def __init__(self, n, intersections):
        self.quorums = dict()
        self.network = []
        size = int((n - 1) * n / 2)
        # These will all be needed but don't work for me
        # containers = [SawtoothContainer() for _ in range(size*intersections*2)]
        # user_keys = [i.user_key() for i in containers]
        # val_keys = [i.user_key() for i in containers]
        # committee_ips = [i.ip() for i in containers]
        containers = range(size*intersections*2)
        keyIndex = 0
        for _ in range (intersections):
            for i in range(n-1):
                offset = 1
                for _ in range((n-1)-i):
                    newEngineId = int(keyIndex/2)
                    newClusterEngine = ClusterEngine(i, offset + i, newEngineId, containers[keyIndex], containers[keyIndex + 1])
                    self.addpeer(newClusterEngine)
                    self.network.append(newClusterEngine)
                    offset = offset + 1
                    keyIndex += 2
    
    def addpeer(self, Engine):
        self.joinQuorums(Engine)
        Aid = Engine.instanceAid
        Bid = Engine.instanceBid
        if Aid in self.quorums:
            self.quorums[Aid].append(Engine.id)
        else:
            self.quorums[Aid] = list()
            self.quorums[Aid].append(Engine.id)
        
        if Bid in self.quorums:
            self.quorums[Bid].append(Engine.id)
        else:
            self.quorums[Bid] = list()
            self.quorums[Bid].append(Engine.id)

    def joinQuorums(self, Engine):
        Aid = Engine.instanceAid
        Bid = Engine.instanceBid
        if Aid in self.quorums:
            for i in range(len(self.quorums[Aid])):
                NeighborsQuorum = self.network[self.quorums[Aid][i]].addNeighbor(Aid, Bid, Engine.id)
                Engine.addNeighbor(Aid, NeighborsQuorum, self.network[self.quorums[Aid][i]].id)

        if Bid in self.quorums:
            for i in range(len(self.quorums[Bid])):
                NeighborsQuorum = self.network[self.quorums[Bid][i]].addNeighbor(Bid, Aid, Engine.id)
                Engine.addNeighbor(Bid, NeighborsQuorum, self.network[self.quorums[Bid][i]].id)

    def inserttransaction(self, quorum, tx):
        result = self.network[choice(self.quorums[quorum])].inserttransaction(tx)
        if result != -1:
            self.network[result].inserttransaction(tx)

test = main(5, 1)
tx1 = Transaction(0,0)
tx2 = Transaction(3,1)
test.inserttransaction(0,tx1)
test.inserttransaction(0, tx2)