from kivy.graphics import Rectangle, Line, Ellipse, Color
from kivy.core.window import Window

from .common import BackgroundColor, RectangleBorder
from .common import draw_text, draw_circle

from game.board import Board
from game.tree import NodeKey
from theme import Theme
import math

class SimpleBoardPanelWidget(RectangleBorder):
    def __init__(self, **kwargs):
        super(SimpleBoardPanelWidget, self).__init__(**kwargs)

    def draw_circle(self, x, y, color=None, **kwargs):
        draw_circle(
            (self.gridpos_x[x], self.gridpos_y[y]),
            self.stone_size,
            color, **kwargs
        )

    def on_size(self, *args):
        self.draw_board_only()
        self.draw_stone_on_board()

    def draw_board_only(self):
        board_size = self.board.board_size
        X_LABELS = self.board.X_LABELS

        self.canvas.before.clear()
        with self.canvas.before:
            # board rectangle
            square_size = min(self.width, self.height)
            rect_pos = (self.center_x - square_size/2, self.center_y - square_size/2)
            Color(*Theme.BOARD_COLOR.get())
            board_rect = Rectangle(pos=rect_pos, size=(square_size, square_size))

            # grid lines
            margin = Theme.BOARD_MARGIN
            self.grid_size = board_rect.size[0] / (board_size - 1 + 1.5 * margin)
            self.stone_size = self.grid_size * Theme.STONE_SIZE
            self.gridpos = [math.floor((margin + i) * self.grid_size + 0.5) for i in range(board_size)]
            self.gridpos_x = [v + board_rect.pos[0] for v in self.gridpos]
            self.gridpos_y = [v + board_rect.pos[1] for v in self.gridpos]

            line_color = Theme.LINE_COLOR
            Color(*line_color.get())
            lo_x, hi_x = self.gridpos_x[0], self.gridpos_x[-1]
            lo_y, hi_y = self.gridpos_y[0], self.gridpos_y[-1]
            for i in range(board_size):
                Line(points=[(self.gridpos_x[i], lo_y), (self.gridpos_x[i], hi_y)])
                Line(points=[(lo_x, self.gridpos_y[i]), (hi_x, self.gridpos_y[i])])

            # star points
            star_scale = (self.grid_size/self.stone_size) * Theme.STARPOINT_SIZE
            for x, y in [ (idx % board_size, idx // board_size) for idx in range(board_size * board_size)]:
                if self.board.is_star((x,y)):
                    self.draw_circle(
                        x, y, line_color.get(), scale=star_scale)

            # coordinates
            lo = self.gridpos[0]
            for i in range(board_size):
                draw_text(
                    pos=(self.gridpos_x[i], lo_y - lo / 2),
                    text=X_LABELS[i],
                    color=(0.25, 0.25, 0.25),
                    font_size=self.grid_size / 1.5)
                draw_text(
                    pos=(lo_x - lo / 2, self.gridpos_y[i]),
                    text=str(i + 1),
                    color=(0.25, 0.25, 0.25),
                    font_size=self.grid_size / 1.5)

    def draw_stone_on_board(self):
        self.canvas.clear()
        with self.canvas:
            # stones on board
            stone_colors = Theme.STONE_COLORS
            laststone_colors = Theme.LAST_COLORS
            outline_colors = Theme.OUTLINE_COLORS
            light_col = (0.99, 0.99, 0.99)
            stones_coord = self.board.get_stones_coord()

            for color, x, y in stones_coord:
                self.draw_circle(
                    x, y,
                    stone_colors[color].get(),
                    outline_color=outline_colors[color].get())

                if self.board.is_last_move((x,y)):
                    self.draw_circle(x, y, laststone_colors[color].get(), scale=0.35)


class BoardPanelWidget(SimpleBoardPanelWidget):
    def __init__(self, **kwargs):
        super(BoardPanelWidget, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.on_mouse_pos)
        self.pv_start_pos = None
        self.forbid_pv = False
        self.ghost_stone = None
        self.last_board_content_tag = None
        self.wait_for_comp_move = False

    def on_mouse_pos(self, *args): # https://gist.github.com/opqopq/15c707dc4cffc2b6455f
        if self.get_root_window():  # don't proceed if I'm not displayed <=> If have no parent
            pos = args[1]
            relative_pos = self.to_widget(*pos)

            prev_pv_pos = self.pv_start_pos
            self.pv_start_pos = None
            if self.collide_point(*relative_pos):
                analysis = self.tree.get_val().get("analysis")
                xd, xp, yd, yp = self._find_closest(relative_pos)

                if analysis and max(yd, xd) < self.grid_size / 2:
                    for info in analysis.get_sorted_moves():
                        if not info["move"].is_move():
                            continue
                        x, y = info["move"].get()
                        if x == xp and y == yp:
                            self.pv_start_pos = (x, y)
            if prev_pv_pos != self.pv_start_pos:
                self.tree.update_tag()

    def on_touch_down(self, touch):
        if self.should_lock_board():
            return
        if "button" in touch.profile and touch.button == "right":
            self.forbid_pv = True
            if self.pv_start_pos:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "left":
            xd, xp, yd, yp = self._find_closest(touch.pos)
            prev_ghost = self.ghost_stone
            if self.board.num_passes < 2 and \
                   self.board.legal((xp, yp)) and \
                   max(yd, xd) < self.grid_size / 2:
                self.ghost_stone = (xp, yp)
            else:
                self.ghost_stone = None
            if prev_ghost != self.ghost_stone:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "scrolldown":
            self.undo_move()
        if "button" in touch.profile and touch.button == "scrollup":
            self.redo_move()

    def on_touch_move(self, touch): # on_motion on_touch_move
        return self.on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.should_lock_board():
            return
        if "button" in touch.profile and touch.button == "right":
            self.forbid_pv = False
            if self.pv_start_pos:
                self.tree.update_tag()
        if "button" in touch.profile and touch.button == "left":
            if self.ghost_stone:
                xd, xp, yd, yp = self._find_closest(touch.pos)
                if self.board.num_passes < 2 and \
                       self.board.legal((xp, yp)) and \
                       max(yd, xd) < self.grid_size / 2:
                    col = self.board.get_gtp_color(self.board.to_move)
                    vtx = self.board.get_gtp_vertex((xp, yp))
                    self.handle_play_move(col, vtx)
                    self.ghost_stone = None
            if self.board.num_passes >= 2:
                xd, xp, yd, yp = self._find_closest(touch.pos)
                if max(yd, xd) < self.grid_size / 2:
                    self.board.mark_dead((xp, yp))
                self.tree.get_val()["board"] = self.board.copy()
                self.tree.update_tag()

    def on_size(self, *args):
        self.draw_board_only()
        self.last_board_content_tag = None

    def undo_move(self):
        succ = self.tree.backward()
        if succ:
            self.board.copy_from(self.tree.get_val()["board"])
            self.engine.do_action({ "action" : "undo" })
        return succ

    def redo_move(self):
        succ = self.tree.forward()
        if succ:
            col, vtx = self.tree.get_key().unpack()
            self.board.copy_from(self.tree.get_val()["board"])
            self.engine.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )
        return succ

    def should_lock_board(self):
        self.comp_side = self.config.get("game")["comp"]
        if self.comp_side.lower() == "na" or \
               self.board.num_passes >= 2:
            return False
        if self.comp_side.lower() == "b" and \
               self.board.to_move == Board.BLACK:
            return True
        if self.comp_side.lower() == "w" and \
               self.board.to_move == Board.WHITE:
            return True
        return False

    def handle_engine_move(self):
        # acquire engine to genrate move
        if self.should_lock_board() and \
               not self.wait_for_comp_move:
            col = self.board.get_gtp_color(self.board.to_move)
            self.engine.do_action(
                { "action" : "genmove", "color" : col}
            )
            self.wait_for_comp_move = True

        # play the move on the board if possible
        compvtx = self.tree.get_val().get("move")
        if self.wait_for_comp_move and \
               self.should_lock_board() and \
               compvtx:
            self.handle_play_move(
                self.board.get_gtp_color(self.board.to_move), compvtx, False)
            self.wait_for_comp_move = False

        return self.wait_for_comp_move

    def handle_play_move(self, col, vtx, use_engine=True):
        if use_engine:
            self.engine.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )
        self.board.play(vtx, to_move=col)
        self.tree.add_and_forward(
            NodeKey(col, vtx), { "board" : self.board.copy() }
        )

    def draw_influence(self, x, y, color, scale):
        Color(*color)
        sz = self.grid_size * scale
        Rectangle(pos=(self.gridpos_x[x] - sz/2, self.gridpos_y[y] - sz/2), size=(sz, sz))

    def draw_board_contents(self):
        curr_tag = self.tree.get_tag()
        if self.last_board_content_tag == curr_tag:
            return
        self.last_board_content_tag = curr_tag
        board = self.tree.get_val()["board"]

        # synchronize PV board
        forbid_pv = self.forbid_pv or \
                        not self.config.get("engine")["pv"]
        analysis = self.tree.get_val().get("analysis")
        show_pv_board = not forbid_pv and \
                            not self.pv_start_pos is None and \
                            board.get_stone(self.pv_start_pos) == Board.EMPTY and \
                            analysis is not None
        main_info = None
        if show_pv_board:
            board = board.copy()
            pv_list = list()
            for info in analysis.get_sorted_moves():
                if info["move"].is_move() and \
                       info["move"].get() == self.pv_start_pos:
                    main_info = info
                    pv_list = info["pv"]
            for vtx in pv_list:
                try:
                    board.play(vtx)
                except Exception:
                    # not a legal move
                    break

        self.canvas.clear()
        with self.canvas:
            # stones on board
            stone_colors = Theme.STONE_COLORS
            laststone_colors = Theme.LAST_COLORS
            outline_colors = Theme.OUTLINE_COLORS
            light_col = (0.99, 0.99, 0.99)
            stones_coord = board.get_stones_coord()

            last_move = None
            for color, x, y in stones_coord:
                if board.is_last_move((x,y)):
                    last_move = (x, y, laststone_colors[color])
                self.draw_circle(
                    x, y,
                    stone_colors[color].get(),
                    outline_color=outline_colors[color].get())
            if show_pv_board:
                if not main_info is None:
                    self.draw_ownermap(main_info.get("ownership"))
                unique_pv_buf = set()
                for idx, vtx in reversed(list(enumerate(pv_list))):
                    if not vtx.is_move():
                        continue
                    x, y = vtx.get()
                    if (x, y) in unique_pv_buf:
                        continue
                    unique_pv_buf.add((x,y))
                    col = board.get_invert_color(board.get_stone((x,y)))
                    if col in [Board.BLACK, Board.WHITE]:
                        draw_text(
                            pos=(self.gridpos_x[x], self.gridpos_y[y]),
                            text="{}".format(idx+1),
                            color=stone_colors[col].get(),
                            font_size=self.grid_size / 2.5)
            else:
                self.draw_auxiliary_contents()
                self.draw_analysis_contents()
            if last_move:
                x, y, color = last_move
                self.draw_circle(x, y, color.get(), scale=0.35)

    def draw_auxiliary_contents(self):
        board = self.tree.get_val()["board"]
        to_move = board.to_move
        stone_colors = Theme.STONE_COLORS
        outline_colors = Theme.OUTLINE_COLORS

        # hover next move ghost stone
        ghost_alpha = Theme.GHOST_ALPHA
        if self.ghost_stone:
            self.draw_circle(
                *self.ghost_stone,
                stone_colors[to_move].bind_alpha(ghost_alpha).get())

        # children of current moves in undo / review
        undo_colors = Theme.UNDO_COLORS
        children_keys = self.tree.get_children_keys()
        for k in children_keys:
            col, vtx = k.unpack()
            if not vtx.is_move():
                continue
            x, y = vtx.get()
            self.draw_circle(
                x, y,
                outline_color=undo_colors[0 if col.is_black() else 1].get())

        if board.num_passes >= 2:
            # final positions
            get_deadstones_coord = board.get_deadstones_coord()
            for col, x, y in get_deadstones_coord:
                self.draw_circle(
                    x, y,
                    stone_colors[col].bind_alpha(ghost_alpha).get(),
                    outline_color=outline_colors[col].get())

            finalpos_coord = board.get_finalpos_coord()
            for col, x, y in finalpos_coord:
                if col == Board.EMPTY:
                    continue
                self.draw_influence(x, y, stone_colors[col].bind_alpha(0.65).get(), 0.55)

    def draw_analysis_contents(self):
        board = self.tree.get_val()["board"]
        analysis = self.tree.get_val().get("analysis")
        ownership = self.config.get("engine")["use_ownership"]
        show = self.config.get("engine")["show"]
        forbidmap = list()

        if board.num_passes < 2 and analysis:
            sorted_moves = analysis.get_sorted_moves()
            best_color = (0.3, 0.85, 0.85)
            norm_color = (0.1, 0.75, 0.1)
            tot_visits = sum(info["visits"] for info in sorted_moves)
            max_visits = max(info["visits"] for info in sorted_moves)

            for info in sorted_moves:
                if show == "NA" or not info["move"].is_move():
                    # we can only draw the move on the board
                    continue
                x, y = info["move"].get()
                visits = info["visits"]
                visit_ratio = visits / max_visits

                alpha_factor = math.pow(visit_ratio, 0.3)
                alpha = alpha_factor * 0.75 + (1. - alpha_factor) * 0.1

                eval_factor = math.pow(visit_ratio, 4.)
                eval_color = [ eval_factor * b + (1. - eval_factor) * n for b, n in zip(best_color, norm_color) ]
                self.draw_circle(x, y, (*eval_color, alpha))

                if alpha > 0.25:
                    # draw analysis text on the candidate circle
                    show_lines = 0
                    text_str = str()
                    for show_mode in show.split("+"):
                        if show_mode in ["W", "D", "S", "V", "P"] and len(text_str) > 0:
                            show_lines += 1
                            text_str += "\n"
                        if "W" == show_mode:
                            text_str += "{}".format(round(info["winrate"] * 100))
                        if "D" == show_mode:
                            text_str += "{}".format(round(info["drawrate"] * 100))
                        elif "S" == show_mode:
                            text_str += "{:.1f}".format(info["scorelead"])
                        elif "V" == show_mode:
                            if visits >= 1e11:
                                text_str += "{:.0f}b".format(visits/1e9)
                            elif visits >= 1e9:
                                text_str += "{:.1f}b".format(visits/1e9)
                            elif visits >= 1e8:
                                text_str += "{:.0f}m".format(visits/1e6)
                            elif visits >= 1e6:
                                text_str += "{:.1f}m".format(visits/1e6)
                            elif visits >= 1e5:
                                text_str += "{:.0f}k".format(visits/1e3)
                            elif visits >= 1e3:
                                text_str += "{:.1f}k".format(visits/1e3)
                            else:
                                text_str += "{}".format(visits)
                        elif "P" == show_mode:
                            text_str += "{:.1f}".format(info["prior"] * 100)
                        elif "R" == show_mode:
                            text_str += "{:.1f}".format((visits/tot_visits) * 100)

                    show_lines = min(show_lines, 2)
                    show_lines = max(show_lines, 0)
                    font_size_div = [3.0, 3.25, 4.05][show_lines]
                    draw_text(
                        pos=(self.gridpos_x[x], self.gridpos_y[y]),
                        text=text_str,
                        color=(0.05, 0.05, 0.05),
                        font_size=self.grid_size / font_size_div)
                    forbidmap.append((x,y))
                else:
                    # fade candidate circle and draw aura
                    self.draw_circle(
                        x, y,
                        outline_color=(0.5, 0.5, 0.5, alpha),
                        outline_scale=0.05,
                        outline_align="center")

            root_info = analysis.get_root_info()
            if not root_info is None:
                self.draw_ownermap(root_info.get("ownership"), forbidmap)

    def draw_ownermap(self, ownermap, forbidmap=[]):
        if ownermap is None:
            return
        board = self.tree.get_val()["board"]
        stone_colors = Theme.STONE_COLORS
        board_size = board.board_size
        to_move = board.to_move

        rowmajor_idx = 0
        for y in range(board_size)[::-1]:
            for x in range(board_size):
                owner = ownermap[rowmajor_idx]
                col = to_move if owner > 0.0 else self.board.get_invert_color(to_move)
                influ_factor = math.pow(math.fabs(owner), 0.75)
                influ_alpha = influ_factor * 0.65
                influ_size = influ_factor * 0.55 + (1.0 - influ_factor) * 0.25

                if not (x, y) in forbidmap:
                    self.draw_influence(
                        x, y,
                        stone_colors[col].bind_alpha(influ_alpha).get(),
                        influ_size)
                rowmajor_idx += 1

    def _find_closest(self, pos):
        x, y = pos
        xd, xp = sorted([(abs(p - x), i) for i, p in enumerate(self.gridpos_x)])[0]
        yd, yp = sorted([(abs(p - y), i) for i, p in enumerate(self.gridpos_y)])[0]
        return xd, xp, yd, yp