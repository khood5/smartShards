from src.api.constants import TRANSACTION_KEY, TRANSACTION_VALUE, QUORUM_ID
import json


class Transaction:
    def __init__(self, quorum="", key="", value=""):
        self.quorum_id = quorum
        self.key = key
        self.value = value

    def id(self):
        # this is the id of the destination quorum
        # the destination quorum is the quorum responsible for
        # confirming the tx
        return self.quorum_id

    def to_json(self):
        return json.loads(json.dumps({QUORUM_ID: self.quorum_id,
                                      TRANSACTION_KEY: self.key,
                                      TRANSACTION_VALUE: self.value}))

    def load_from_json(self, json_data):
        self.quorum_id = json_data[QUORUM_ID]
        self.key = json_data[TRANSACTION_KEY]
        self.value = json_data[TRANSACTION_VALUE]
