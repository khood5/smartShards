from src.SawtoothPBFT import SawtoothContainer


class SinglePeer:

    def __init__(self, network):
        self.__instance = SawtoothContainer(network=network)

    def join(self, ips):
        self.__instance.join_sawtooth(ips)

    def make_genesis(self, val_keys, usr_keys):
        self.__instance.make_genesis(val_keys, usr_keys)

    def submit_tx(self, key, value):
        self.__instance.submit_tx(key,value)

    def ip(self):
        return self.__instance.ip()

    def val_key(self):
        return self.__instance.val_key()

    def usr_key(self):
        return self.__instance.user_key()

    def get_tx(self, key):
        return self.__instance.get_tx(key)

    def blocks(self):
        blocks = self.__instance.blocks()
        print("blocks: {}".format(blocks))
        if blocks:
            return blocks
        else:
            return {'data': "This peer has no blocks"}
