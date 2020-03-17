import docker


class SawtoothContainer:

    def start(ports, neighborhood):
        client = docker.from_env()
        container = client.containers.run('sawtooth:base',
                                          detach=True)
        # start process woth ports and neighborhood
        # return PID

    def end(p):
        pass
        # PID = p.PID
        # stop process with matching PID

    def restart(prvProcess):
        pass
        # ports
        # ports[com] = p.component
        # ports[cons] = p.consensus
        # ports[net] = p.network
        #
        # list < connStr > neighborhood = p.neighbors
        #
        # endProcess(p)
        # newProcess = startProcess(ports, neighborhood)
        #
        # PBFT
        # inst
        # inst.PID = newProcess
        # inst.envi = ports
        # return inst
