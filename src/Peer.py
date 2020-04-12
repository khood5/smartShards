import SawtoothPBFT


class Peer:
    instanceA = None
    instanceB = None


    def __init__(self, sawtooth1, sawtooth2):
        self.instanceA = sawtooth1
        self.instanceB = sawtooth2

    def inserttransaction(self, tx):
        print("Submitted")