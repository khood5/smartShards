# smartShards

Smart Shards is a sharded blockchain with a foucus on elementating the need for a referance committee. A blockchain is a distrbuted leger maintained by a set of processing units called peers. These are commonly PC's distrbuted over a large network such as the internet and orgnized as a peer to peer netwrok. Peers must reach conesnus on each entery into the blockchain, that is the majority of peer must validate an entry before it is added to the ledger. Blockchains suffer from poor thoughput (validated/submit entries) and high waiting time (time between submition and validation of en entry) when there is a large number of peers. To overcome this, peers are often seprated into smaller subsets called committees. Each committee preforms its own conesnus and thus committees can work in parllel to validate entires. Ognization of the peers into committees relies on a referance committee. The referance committee is a special committees used to determain which peers have membership to which committees, route transactions, handle churn and often are used to check other committess for correctness. This creates a bottleneck in the system,               

Many other popular hsarding algorthm sush as Elastico, OmniLedger and RapidChain relay on a referance committee to orgnize peers into committees 

This is the implementation of smart shards. It is built with two parts a manger and a consensus algorithm. We use the implementation of PBFT in the sawtooth project. Our manager will organize PBFT into smart shards.

Sawtooth Documentation: https://sawtooth.hyperledger.org/docs/core/nightly/1-2/


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
