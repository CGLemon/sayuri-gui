from board import Board
from tree import Tree, NodeKey
from datetime import datetime

def _load_sgf_based(sgf, sgf_board, sgf_tree, raise_err):
    def process_key_value(key, val, board, tree):
        def as_vertex_move(m, board):
            if len(m) == 0 or m == "tt":
                return board.PASS_VERTEX
            x = ord(m[0]) - ord('a')
            y = ord(m[1]) - ord('a')
            y = board.board_size - 1 - y
            return board.get_vertex(x, y)

        if key == "SZ":
            board_size = int(val)
            board.reset(board_size, board.komi, board.scoring_rule)
            if not tree is None:
                tree.get_val()["board"].copy_from(board)
        elif key == "KM":
            komi = float(val)
            board.reset(board.board_size, komi, board.scoring_rule)
            if not tree is None:
                tree.get_val()["board"].copy_from(board)
        elif key == "RU":
            scoring_rule = board.transform_scoring_rule(val)
            board.reset(board.board_size, board.komi, scoring_rule)
            if not tree is None:
                tree.get_val()["board"].copy_from(board)
        elif key == "C":
            if not tree is None:
                tree.get_val()["comment"] = val
        elif key == "B":
            vtx = board.get_gtp_vertex(as_vertex_move(val, board))
            col = board.get_gtp_color(board.BLACK)
            board.play(vtx, to_move=col)
            if not tree is None:
                tree.add_and_forward(NodeKey(col, vtx), { "board" : board.copy() })
        elif key == "W":
            vtx = board.get_gtp_vertex(as_vertex_move(val, board))
            col = board.get_gtp_color(board.WHITE)
            board.play(vtx, to_move=col)
            if not tree is None:
                tree.add_and_forward(NodeKey(col, vtx), { "board" : board.copy() })
        elif key == "AB" or key == "AW":
            raise Exception("Do not support for AB/AW tag in the SGF file.")
    try:
        level = 0
        idx = 0
        node_cnt = 0
        key = str()
        while idx < len(sgf):
            c = sgf[idx]
            idx += 1;

            if c == '(':
                level += 1
            elif c == ')':
                level -= 1

            if c in ['(', ')', '\t', '\n', '\r'] or level != 1:
                continue
            elif c == ';':
                node_cnt += 1
            elif c == '[':
                end = sgf.find(']', idx)
                val = sgf[idx:end]
                process_key_value(key, val, sgf_board, sgf_tree)
                key = str()
                idx = end+1
            else:
                key += c
    except Exception as err:
        if raise_err:
            raise err

def load_sgf_as_tree(sgf, raise_err=False):
    board = Board(19, 7.5, Board.SCORING_AREA)
    tree = Tree({ "board" : board.copy() })
    try:
        _load_sgf_based(sgf, board, tree, raise_err)
    except Exception as err:
        if raise_err:
            raise err
        return None
    return tree

def load_sgf_as_board(sgf, raise_err=False):
    board = Board(19, 7.5, Board.SCORING_AREA)
    tree = Tree({ "board" : board.copy() })
    try:
        _load_sgf_based(sgf, board, tree, raise_err)
    except Exception as err:
        if raise_err:
            raise err
        return None
    return board

def transform_tree_to_sgf(tree, black="NA", white="NA", result=None):
    board = tree.get_val()["board"]
    sgf = "(;GM[1]FF[4]SZ[{}]KM[{}]RU[{}]PB[{}]PW[{}]DT[{}]".format(
              board.board_size, board.komi,
              board.transform_scoring_rule(board.scoring_rule),
              black, white,
              datetime.now().strftime("%Y-%m-%d-%H:%M:%S"))
    if result:
        sgf += "RE[{}]".format(result)

    for node in tree.get_root_mainpath():
        if not node.get_key() is None:
            col, vtx = node.get_key().unpack()
            cstr = "B" if col.is_black() else "W"
            if vtx.is_pass():
                vstr = "tt" if board.board_size <= 19 else ""
            elif vtx.is_resign():
                pass
            else:
                x, y = vtx.get()
                y = board.board_size - 1 - y
                vstr = str()
                vstr += chr(x + ord('a'))
                vstr += chr(y + ord('a'))
            sgf += ";{}[{}]".format(cstr, vstr)
        if not node.get_val().get("comment") is None:
            sgf += "C[{}]".format(node.get_val()["comment"])
    sgf += ")"
    return sgf
