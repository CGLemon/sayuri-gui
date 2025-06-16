import random

class NodeKey:
    def __init__(self, color, vertex):
        self.color = color
        self.vertex = vertex

    def unpack(self):
        return self.color, self.vertex

    def __eq__(self, other):
        return self.__hash__() == hash(other)

    def __str__(self):
        return "{}-{}".format(self.color, self.vertex)

    def __hash__(self):
        ret = hash(self.__str__())
        return ret

class Node:
    def __init__(self, val, key=None, parent=None, depth=0):
        self.val = val
        self.key = key
        self.depth = depth
        self.parent = parent
        self.default = None
        self.children = dict()
        self.tag = random.randint(0, 18446744073709551615)

    def try_add_child(self, key, val):
        if not key in self.children.keys():
            self.children[key] = Node(val, key, self, self.depth+1)
        self.default = self.children[key]

    def update_tag(self):
        self.tag = random.randint(0, 18446744073709551615) # range of uint64

    def get_tag(self):
        return self.tag

    def get_val(self):
        return self.val

    def get_depth(self):
        return self.depth

    def get_children_keys(self):
        return self.children.keys()

    def get_children_val(self, key):
        if self.children.get(key) is None:
            return None
        return self.children[key].get_val()

    def get_key(self):
        return self.key

class Tree:
    def __init__(self, val):
        self.root = Node(val)
        self.curr = self.root

    def reset(self, val):
        self.root.val = val
        self.root.key = None
        self.root.depth = 0
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

    def get_depth(self):
        return self.curr.depth

    def get_parent(self):
        return self.curr.parent

    def get_root_mainpath(self):
        path = self.root
        while path:
            yield path
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

    def copy_from(self, other):
        self.reset(other.root.get_val())
        src_nodes = [ other.root ]
        dst_nodes = [ self.root ]
        while len(dst_nodes) > 0:
            src = src_nodes.pop(-1)
            dst = dst_nodes.pop(-1)
            for key in src.get_children_keys():
                dst.try_add_child(key, src.get_children_val(key))
            for key in src.get_children_keys():
                src_nodes.append(src.children[key])
                dst_nodes.append(dst.children[key])
