class portmanager:
    _instance = None

    class __Manger:
        available = list()

        def __init__(self):
            pass

        def setRange(self, start, end):
            self.available.clear()
            self.available.extend(range(start,end))

        def getPort(self):
            return self.available.pop()

    def __new__(self):
        if self._instance is None:
            self._instance = self.__Manger()
        return self._instance

    def setRnage(self, start, end):
        self._instance.SetRange(start,end)

    def getPort(self):
        return self._instance.getPort()






