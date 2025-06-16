from .gtp import GtpVertex

class AnalysisParser(list):
    SUPPORTED_KEYS = [
        "info",
        "move",
        "visits",
        "winrate",
        "drawrate",
        "scorelead",
        "prior",
        "lcb",
        "order",
        "pv",
        "ownership"
    ]

    def __init__(self, data):
        super(AnalysisParser, self).__init__()
        self.data = data
        self.datalist = data.split()
        self._parse()

    def get_sorted_moves(self):
        sorted_moves = list()
        for info in self:
            if not info.get("order") is None:
                sorted_moves.append(info)
        sorted_moves.sort(key=lambda x:x["order"], reverse=False)
        return sorted_moves

    def get_root_info(self):
        for info in self:
            if not info.get("move") is None and \
                    info.get("move").is_null():
                return info
        return None

    def _back(self):
        self.idx -= 1

    def _next_token(self):
        if self.idx >= len(self.datalist):
            return None
        token = self.datalist[self.idx]
        self.idx += 1
        return token.lower()

    def _next_number(self):
        t = self._next_token()
        return self._token_to_number(t)

    def _token_to_number(self, t):
        try:
            return int(t)
        except ValueError:
            return float(t)

    def _get_sequential_tokens(self, trans_fn=None):
        tokens = list()
        while True:
            token = self._next_token()
            if token == None:
                break
            if token in self.SUPPORTED_KEYS:
                self._back()
                break
            if trans_fn:
                tokens.append(trans_fn(token))
            else:
                tokens.append(token)
        return tokens

    def _parse(self):
        self.idx = 0
        while True:
            token = self._next_token()
            if token == None:
                break
            if token == "info":
                self.append(dict())
            elif token == "move":
                self[-1]["move"] = GtpVertex(self._next_token())
            elif token == "visits":
                self[-1]["visits"] = self._next_number()
            elif token == "winrate":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["winrate"] = num
            elif token == "drawrate":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["drawrate"] = num
            elif token == "scorelead":
                self[-1]["scorelead"] = self._next_number()
            elif token == "prior":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["prior"] = num
            elif token == "lcb":
                num = self._next_number()
                if type(num) == int:
                    num = float(num) / 10000.
                self[-1]["lcb"] = num
            elif token == "order":
                self[-1]["order"] = self._next_number()
            elif token == "pv":
                self[-1]["pv"] = self._get_sequential_tokens(
                    GtpVertex
                )
            elif token == "ownership":
                self[-1]["ownership"] = self._get_sequential_tokens(
                    self._token_to_number
                )
            else:
                pass
