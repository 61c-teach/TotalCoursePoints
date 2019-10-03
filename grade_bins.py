"""
Grade bins.
"""
class GradeBinsError(Exception):
    pass

class Max:
    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Max"

    def __lt__(self, other):
        # For x < y
        return False

    def __le__(self, other):
        # For x <= y
        return isinstance(other, Max)

    def __eq__(self, other):
        # For x == y
        return isinstance(other, Max)

    def __ne__(self, other):
        # For x != y OR x <> y
        return not self == other

    def __gt__(self, other):
        # For x > y
        return not isinstance(other, Max)

    def __ge__(self, other):
        # For x >= y
        return True


class Bin:
    """[min, max)"""
    def __init__(self, id: str, min: float, max: float):
        self.id = id
        self.min = min
        self.max = max

    def __contains__(self, key: float):
        return self.in_bin(key)

    def __str__(self):
        return "{}: [{}, {})".format(self.id, self.min, self.max)
    
    def in_bin(self, value: float) -> bool:
        if self.min is None and self.max is None:
            return True
        if value is None:
            return False
        if self.min is None:
            return value < self.max
        elif self.max is None:
            return value >= self.min
        return value >= self.min and value < self.max

    def in_relative_bin(self, percentage:float, max_points:float):
        return self.in_bin(percentage * max_points)

class GradeBins:
    def __init__(self, bins: list = [], pass_threshold: Bin = None, normal_max_points: float = None):
        self.bins = {}
        mxpts = None
        for b in bins:
            if mxpts is None or b.max > mxpts:
                mxpts = b.max
            self.add_bin(b)

        if normal_max_points is not None:
            mxpts = normal_max_points
        self.normal_max_points = mxpts
        
        if isinstance(pass_threshold, Bin):
            self.pass_threshold = pass_threshold.min
        elif isinstance(pass_threshold, float):
            self.pass_threshold = pass_threshold
        elif isinstance(pass_threshold, int):
            self.pass_threshold = pass_threshold
        else:
            self.pass_threshold = Max()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Grade Bins:\n{}\nPassing Score: {}".format("\n".join(map(str, self.bins.values())), self.pass_threshold)
    
    def add_bin(self, new_bin: Bin) -> None:
        if new_bin.id in self.bins:
            raise ValueError("A bin with the same id ({}) already exists in the GradeBins!".format(new_bin.id))
        # for b in self.bins.values():
            # if  b.min in new_bin or \
            #     b.max in new_bin or \
            #     new_bin.min in b or \
            #     new_bin.max in b:
            #     import ipdb; ipdb.set_trace()
            #     raise ValueError("The new bin {} conflict with an existing bin {}!".format(new_bin, b))
        self.bins[new_bin.id] = new_bin
    
    def remove_bin(self, id: str) -> bool:
        if id in self.bins:
            del self.bins[id]
            return True
        return False

    def in_bin(self, value: float) -> Bin:
        for b in self.bins.values():
            if value in b:
                return b
        return None

    def is_passing(self, value: float) -> bool:
        return value >= self.pass_threshold

    def relative_bin(self, score:float, max_score:float) -> bool:
        if self.normal_max_points is None:
            raise GradeBinsError("There is no max score set!")
        for b in self.bins.values():
            if b.in_relative_bin(score / max_score, self.normal_max_points):
                return b
        return None