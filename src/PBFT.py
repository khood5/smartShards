# connection string (connStr) is a string in the form ~ tcp://203.0.113.0:8800

from src.portmanager import PortManager
from src import SawtoothPBFT

# envi keys
com = 'component'
cons = 'consensus'
net = 'network'


class PBFT:
    envi = dict()
    neighbors = list()
    instance = -1

    def __init__(self):
        self.envi = dict().fromkeys([com, cons, net])

    # PRE: there is no pre-condition
    # POST: an instance of PBFT is running.
    #       it's configuration is stored in envi
    #       its neighbors are stored in neighbors
    def start(self, neighborhood):
        availablePorts = PortManager()
        self.envi[com] = availablePorts.getport()
        self.envi[cons] = availablePorts.getport()
        self.envi[net] = availablePorts.getport()
        self.neighbors = neighborhood
        self.instance = SawtoothPBFT.start(self.envi, neighborhood)

    def submit(self, tx):
        print("submit called")
        pass

