# smartShards
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
