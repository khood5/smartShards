class transaction:
    quorumid = 0
    txNumber = 0

    def __init__(self, quorum, tx):
        self.quorumid = quorum
        self.txNumber = tx