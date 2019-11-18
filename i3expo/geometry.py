class Geometry:
    def __init__(self):
        self.total = Dimension()
        self.grid = Dimension()
        self.space = Dimension()
        self.pad = Dimension()
        self.outer = Dimension()
        self.inner = Dimension()
        self.offset = Dimension()
        self.frame = None


class Dimension:
    def __init__(self, x=None, y=None):
        self.set(x, y)

    def set(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, o):
        if isinstance(o, Dimension):
            return Dimension(self.x + o.x, self.y + o.y)
        else:
            return Dimension(self.x + o, self.y + o)

    def __sub__(self, o):
        return Dimension(self.x - o.x, self.y - o.y)

    def __truediv__(self, o):
        return Dimension(self.x / o.x, self.y / o.y)

    def __str__(self):
        return f'({self.x}, {self.y})'
