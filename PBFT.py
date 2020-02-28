# connection string (connStr) is a string in the form ~ tcp://203.0.113.0:8800

from portmanager import portmanager
import docker_container

# envi keys
com = 'component'
cons = 'consensus'
net = 'network'

class PBFT:
    envi = dict()
    neighbors = list()
    instance = -1

    def __init__(self):
        self.envi.fromkeys([com, cons, net])

    # PRE: there is no pre-condition
    # POST: an instance of PBFT is running.
    #       it's configuration is stored in envi
    #       its neighbors are stored in neighbors
    def startPBFT(self, neighborhood):
        availablePorts = portmanager()
        self.envi[com] = availablePorts.getPort()
        self.envi[cons] = availablePorts.getPort()
        self.envi[net] = availablePorts.getPort()
        self.neighbors = neighborhood
        self.instance = docker_container.startProcess(self.envi, neighborhood)
