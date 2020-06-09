class Transaction:
    def __init__(self, quorum, tx=0):
        self.quorum_id = quorum
        self.tx_number = tx
        self.key = "{}".format(tx)
        self.value = ""

    def id(self):
        # this is the id of the destination quorum
        # the destination quorum is the quorum responsible for
        # confirming the tx
        return self.quorum_id

    def sequence_number(self):
        # this is the sequence number of the transaction
        # no two transactions should ever has the same sequence number
        return self.tx_number
