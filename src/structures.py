import json


class Transaction:
    def __init__(self, quorum="", key="", value=""):
        self.quorum_id = str(quorum)
        self.key = key
        self.value = value

    def id(self):
        # this is the id of the destination quorum
        # the destination quorum is the quorum responsible for
        # confirming the tx
        return str(self.quorum_id)

    def to_json(self):
        return json.loads(json.dumps({"quorum_id": self.quorum_id,
                                      "key": self.key,
                                      "value": self.value}))

    def load_from_json(self, json_data):
        self.quorum_id = json_data["quorum_id"]
        self.key = json_data["key"]
        self.value = json_data["value"]
