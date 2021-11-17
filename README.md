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



#### Other Notes:

If docker refuses connection:
Clear docker instances:
docker ps
docker kill $(docker ps -q)
docker rm $(docker ps -a -q)

Formatted JSON output for blocks:
import json
url = URL_HOST.format(ip=IP_ADDRESS, port='peerDict'['portNumber']) + "/blocks/"
//get results from peer, save it as your_json
parsed = json.loads('your_json')
print(json.dumps(parsed, indent=4, sort_keys=True))


