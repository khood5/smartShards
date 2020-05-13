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


class Quorum:
    def __init__(self, quorum_id: int, members: list):
        self.id = quorum_id
        self.members = members

    def quorum_members(self):
        # this is a list of the ids of all the peers in
        # this quorum
        return self.members

    def quorum_id(self):
        # this is the id of the quorum, no two quorums should
        # have the same id
        return self.quorum_id
