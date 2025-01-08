import random

class NodeKey:
    def __init__(self, color, vertex):
        self.color = color
        self.vertex = vertex

    def unpack(self):
        return self.color, self.vertex

    def __str__(self):
        return "{}-{}".format(self.color, self.vertex)

    def __hash__(self):
        ret = hash(self.__str__())
        return ret

class Node:
    def __init__(self, val, key=None, parent=None):
        self.val = val
        self.key = key
        self.parent = parent
        self.default = None
        self.children = dict()
        self.tag = random.randint(0, 18446744073709551615)

    def try_add_child(self, key, val):
        if not key in self.children.keys():
            self.children[key] = Node(val, key, self)
        self.default = self.children[key]

    def update_tag(self):
        self.tag = random.randint(0, 18446744073709551615) # range of uint64

    def get_tag(self):
        return self.tag

    def get_val(self):
        return self.val

    def get_children_keys(self):
        return self.children.keys()

    def get_key(self):
        return self.key

class Tree:
    def __init__(self, val):
        self.root = Node(val)
        self.curr = self.root

    def reset(self, val):
        self.root.val = val
        self.root.key = None
        self.root.default = None
        self.root.children.clear()
        self.root.update_tag()
        self.curr = self.root

    def get_tag(self):
        return self.curr.get_tag()

    def get_val(self):
        return self.curr.get_val()

    def get_children_keys(self):
        return self.curr.get_children_keys()

    def get_key(self):
        return self.curr.get_key()

    def get_parent(self):
        return self.curr.parent

    def get_root_mainpath(self):
        path = self.root
        while True:
            yield path
            if path.get_tag() == self.curr.get_tag():
                break
            path = path.default

    def add_and_forward(self, key, val):
        self.curr.try_add_child(key, val)
        self.curr = self.curr.default

    def update_tag(self):
        self.curr.update_tag()

    def forward(self):
        if self.curr.default:
            self.curr = self.curr.default
            return True
        return False

    def backward(self):
        if self.curr.parent:
            self.curr = self.curr.parent
            return True
        return False
