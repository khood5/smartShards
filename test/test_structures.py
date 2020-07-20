import unittest
import json
from src.structures import Transaction
import gc

class TestTransactionMethods(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self) -> None:
        gc.collect()

    def test_transaction_to_json(self):
        tx = Transaction("a")
        tx.key = "test"
        tx.value = "999"
        json_data = {"quorum_id": "a", "key": "test", "value": "999"}
        result = tx.to_json()
        self.assertEqual(json_data["quorum_id"], result["quorum_id"])
        self.assertEqual(json_data["key"], result["key"])
        self.assertEqual(json_data["value"], result["value"])

    def test_transaction_from_json(self):
        json_data = json.loads(json.dumps({"quorum_id": "b", "key": "test2", "value": "888"}))
        tx = Transaction("a")
        tx.load_from_json(json_data)
        valid_tx = Transaction("b")
        valid_tx.key = "test2"
        valid_tx.value = "888"
        self.assertEqual(valid_tx.quorum_id, tx.quorum_id)
        self.assertEqual(valid_tx.key, tx.key)
        self.assertEqual(valid_tx.value, tx.value)
