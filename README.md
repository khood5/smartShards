# smartShards

#### Introduction to Smart Shards

Smart Shards is a sharded blockchain with a focus on eliminating the need for a reference committee. A blockchain is a distributed ledger maintained by a set of processing units called peers. These are commonly PC's distributed over a large network such as the internet and organized as a peer to peer network. Entries into the ledger are called transactions, and are submitted via an outside client. Peers must reach consensus on each transaction into the blockchain, that is the majority of peers must validate a transaction before it is added to the ledger. Blockchains suffer from poor throughput (validated/submit transactions) and high waiting time (time between submission and validation of transactions) when there is a large number of peers. To overcome this, peers are often separated into smaller subsets called committees. Each committee performs its own consensus and thus committees can work in parallel to validate transactions. Organization of the peers into committees relies on a reference committee, such as in Elastico, OmniLedger and RapidChain. The reference committee is a special committee used to determain which peers have membership to which committees, route transactions, handle churn and often are used to check other committees for correctness. This creates a bottleneck in the system, introduces a central authority and a single point of failure. Smart Shards elements the need for a reference committee by allowing the committees to achieve all the other previously listed actions together as a single unit but still process transactions in parallel.

This repository is the source code for smart shards. Smart shards is based on Hyperledgers Sawtooth and uses PBFT for distributed consensus. Each smart shared peer runs two instances of Sawtooth. To isolate these instances from each other and to simplify system setup, sawtooth is run inside a docker container. Each smart shared peer maintains and interacts with these sawtooth instances via the Python Docker SDK. Smart shard peers interact with each other via a flask API. Transactions are submitted and retrieved via this same API.

#### Dependency Documentation

Sawtooth Product page: https://sawtooth.hyperledger.org/docs/
Sawtooth Documentation: https://sawtooth.hyperledger.org/docs/core/nightly/1-2/
Sawtooth source code: https://github.com/hyperledger/sawtooth-core

Docker documentation: https://docs.docker.com/

Python Docker SDK documentation: https://docker-py.readthedocs.io/en/stable/

#### System architecture

##### In a single peer
Each smart shards peer is built with the following stack

![This is an image](https://github.com/khood5/smartShards/blob/master/documentation/Smart%20Shards%20Class%20Diagram.png)
 
**Class SawtoothPBF**:  
Wrappers the Sawtooth Docker containers running on the host. It handles communication to that container from the peer, stores some metadata about the container such as it’s IP address and the docker network it is connected to. At its core the class makes available three methods for interacting with the container
```
run_command(self, command: str): runs a command inside the container, such as a bash command, and returns the result.

run_service(self, service_start_command: str): runs a command inside the container, such as a bash command, and returns ***no*** result.

sawtooth_api(self, request: str): makes an HTTP request from inside the container to the sawtooth API, example of a request *http://localhost:8008/blocks*, and returns the result as json
```
The SawtoothPBF also makes available many other methods that serve as a shorthand for some common uses of the above three methods. It also stores all the Sawtooth commands necessary to setup the sawtooth application inside a docker container.

#### Other Notes:

If docker refuses connection:
Clear docker instances:
docker ps
docker kill $(docker ps -q)
docker rm $(docker ps -a -q)

Formatted JSON output for blocks:
import json
url = URL_HOST.format(ip=IP_ADDRESS, port='peerDict'['portNumber']) + "/blocks"
//get results from peer, save it as your_json
parsed = json.loads('your_json')
print(json.dumps(parsed, indent=4, sort_keys=True))

