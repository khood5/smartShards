import docker

def start(ports, neighborhood):
    client = docker.from_env()
    api_client = docker.APIClient(base_url='unix://var/run/docker.sock')
    container = api_client.create_container('ubuntu', 'echo hello world',ports=[1111, 2222],
                host_config=api_client.create_host_config(port_bindings={
                    1111: 4567,
                    2222: None
                })
    )
    resp = client.containers.run()
    print(container)
    #print(resp)
    print("ports:", ports)
    print("neighborhood", neighborhood)

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