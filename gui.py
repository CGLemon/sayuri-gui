import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.graphics import Rectangle, Line, Ellipse, Color

from kivy.properties import ObjectProperty
from kivy.lang import Builder
from kivy.resources import resource_add_path
from kivy.core.window import Window
# from kivy.core.audio import SoundLoader
from kivy.clock import Clock

from kivy.core.text import Label as CoreLabel
from kivy.storage.jsonstore import JsonStore

from tree import Tree, NodeKey
from board import Board
from gtp import GtpEngine, GtpVertex
from analysis import AnalysisParser
from theme import Theme, replace_theme
import sgf_parser
import sys, time, math

from enum import Enum

kivy.config.Config.set("input", "mouse", "mouse,multitouch_on_demand")
DefaultConfig = JsonStore("config.json")

def draw_text(pos, text, color, **kwargs):
    Color(*color)
    label = CoreLabel(text=text, halign="center", valign="middle", bold=True, **kwargs)
    label.refresh()
    Rectangle(
        texture=label.texture,
        pos=(pos[0] - label.texture.size[0] / 2, pos[1] - label.texture.size[1] / 2),
        size=label.texture.size)

def draw_circle(pos, stone_size, color=None, **kwargs):
    outline_color = kwargs.get("outline_color", None)
    scale = kwargs.get("scale", 1.0)
    outline_scale = kwargs.get("outline_scale", 0.065)
    outline_align = kwargs.get("outline_align", "outer")
    group = kwargs.get("group", None)
    stone_size = stone_size * scale
    x, y = pos

    if outline_color:
        align_map = {
            "inner" : 0,
            "center" : 0.5,
            "outer" : 1
        }
        Color(*outline_color)
        width=outline_scale * stone_size
        align_offset = width * align_map.get(outline_align, 0.5)
        Line(circle=(x, y, stone_size + align_offset), width=width, group=group)
    if color:
        Color(*color)
        r = stone_size
        Ellipse(pos=(x - r, y - r), size=(2 * r, 2 * r), group=group)

def comp_side_to_color(comp_side):
    comp_color = None
    if comp_side.lower() == "na":
        comp_color = Board.INVLD
    elif comp_side.lower() == "b":
        comp_color = Board.BLACK
    elif comp_side.lower() == "w":
        comp_color = Board.WHITE
    return comp_color

class GameMode(Enum):
    IDLE = 0
    ANALYZING = 1
    PLAYING = 2

class BackgroundColor(Widget):
    pass

class RectangleBorder(Widget):
    pass

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

class MenuPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(MenuPanelWidget, self).__init__(**kwargs)

    def switch_to_gameio(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-io"
        self.manager.get_screen("game-io").canvas.ask_update()

class ControlsPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(ControlsPanelWidget, self).__init__(**kwargs)
        self.in_end_mode = False

    def update_info(self):
        num_move = self.board.num_move
        if int(self.num_move_label.text) != num_move:
            self.num_move_label.text = str(num_move)

        curr_end = self.board.num_passes >= 2
        if self.in_end_mode and not curr_end:
            self.pass_btn.text = "Pass"
            self.in_end_mode = False
        elif not self.in_end_mode and curr_end:
            self.pass_btn.text = self._get_final_score()
            self.in_end_mode = True
        elif self.in_end_mode and curr_end:
            # may be update the dead stones so we keep to update
            # the final score.
            self.pass_btn.text = self._get_final_score()

    def _get_final_score(self):
        diff = self.board.compute_finalscore(Board.BLACK)
        text = str()
        if abs(diff) < 0.1:
            text = "Draw"
        elif diff > 0.0:
            text = "B+{}".format(diff)
        elif diff < 0.0:
            text= "W+{}".format(-diff)
        return text

    def play_pass(self):
        if self.board.num_passes < 2 and \
               self.board.legal(Board.PASS_VERTEX):
            col = self.board.get_gtp_color(self.board.to_move)
            vtx = GtpVertex("pass")
            self.engine.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )
            self.board.play(vtx, to_move=col)
            self.tree.add_and_forward(
                NodeKey(col, vtx), { "board" : self.board.copy() }
            )

    def undo(self, t=1):
        for _ in range(t):
            if not self.board_panel.undo_move():
                break

    def redo(self, t=1):
        for _ in range(t):
            if not self.board_panel.redo_move():
                break

    def switch_to_gamesetting(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-setting"
        self.manager.get_screen(self.manager.current).sync_config()
        self.manager.get_screen(self.manager.current).canvas.ask_update()

    def switch_to_gameanalysis(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-analysis"
        self.manager.get_screen(self.manager.current).sync_config()
        self.manager.get_screen(self.manager.current).canvas.ask_update()

class GraphPanelWidget(BoxLayout, BackgroundColor, RectangleBorder):
    def __init__(self, **kwargs):
        super(GraphPanelWidget, self).__init__(**kwargs)

    def _get_mainpath_stats(self, tree):
        pathinfo = list()
        for node in tree.get_root_mainpath():
            analysis = node.get_val().get("analysis")
            board = node.get_val()["board"]
            if not analysis is None:
                pathinfo.append((board, analysis.get_sorted_moves()[0]))
            else:
                pathinfo.append((board, None))
        depth = min(tree.get_depth(), len(pathinfo) - 1)

        # Our aim is to determine the optimal analysis results (such as winrate,
        # scorelead, etc.) for every move. Should the current board position lack
        # specific analysis data, we will default to the most recent analysis results
        # obtained previously."
        blackwinrate, blackscore, drawrate, no_stats = 0.5, 0.0, 1.0, True
        stats_history = list()
        for board, info in reversed(pathinfo):
            col = board.get_gtp_color(board.to_move)
            if not info is None:
                blackwinrate = info["winrate"] if col.is_black() else 1.0 - info["winrate"]
                blackscore = info["scorelead"] if col.is_black() else -info["scorelead"]
                drawrate = info["drawrate"]
                no_stats &= False
            bestmove = 0.0 if info is None else info["move"]
            bestpolicy = None if info is None else info["prior"]
            stats_history.append(
                {"blackwinrate" : blackwinrate,
                 "blackscore" : blackscore,
                 "drawrate" : drawrate,
                 "bestpolicy": bestpolicy,
                 "bestmove" : bestmove,
                 "valid" : not no_stats}
            )
        stats_history.reverse()
        return stats_history, depth

    def update_graph(self, tree):
        if self.engine.get_mode() == GameMode.PLAYING:
            self.opacity = 0
            return
        self.opacity = 1
        stats_history, depth = self._get_mainpath_stats(tree)
        blackwinrate_text = "{:3.1f}%".format(0.5 * 100.0)
        bestmove_text = "{}".format(None)

        self.canvas.clear()
        with self.canvas:
            graph_pos = (self.pos[0],  self.pos[1])
            graph_size = (self.width, self.height)

            valid = False
            showdepth = depth
            while showdepth >= 0 and not valid:
                stats = stats_history[showdepth]
                blackwinrate, drawrate, valid =\
                    stats["blackwinrate"], stats["drawrate"], stats["valid"]
                showdepth -= 1

            if self.engine.get_mode() != GameMode.ANALYZING and depth != showdepth+1:
                valid = False

            margin = 0.2
            text_leftpos = [
                self.pos[0] + self.width * margin/2.0,
                self.pos[1] + self.height/2.0
            ]
            # text_rightpos = [
            #     self.pos[0] + self.width * (1.0 - margin/2.0),
            #     self.pos[1] + self.height/2.0
            # ]
            if valid:
                blackbar_ratio = blackwinrate - drawrate/2
                drawbar_ratio = drawrate
                whitebar_ratio = 1.0 - (blackwinrate + drawrate/2)

                bar_xpos = [
                    graph_pos[0],
                    graph_pos[0] + blackbar_ratio * graph_size[0],
                    graph_pos[0] + (blackbar_ratio + drawbar_ratio) * graph_size[0],
                    graph_pos[0] + (blackbar_ratio + drawbar_ratio + whitebar_ratio) * graph_size[0]
                ]

                Color(*Theme.BLACK_WINRATE_COLOR.get())
                Rectangle(
                    pos=(bar_xpos[0], graph_pos[1]),
                    size=(bar_xpos[1] - bar_xpos[0], graph_size[1])
                )
                Color(*Theme.DRAWRATE_COLOR.get())
                Rectangle(
                    pos=(bar_xpos[1], graph_pos[1]),
                    size=(bar_xpos[2] - bar_xpos[1], graph_size[1])
                )
                Color(*Theme.WHITE_WINRATE_COLOR.get())
                Rectangle(
                    pos=(bar_xpos[2], graph_pos[1]),
                    size=(bar_xpos[3] - bar_xpos[2], graph_size[1])
                )
                text_1pos = [
                    bar_xpos[-1] + self.width * margin/2.0,
                    graph_pos[1] + self.height/2.0
                ]
                blackwinrate_text = "{:3.1f}%".format(blackwinrate * 100.0)
                bestmove_text = str(stats["bestmove"])
            draw_text(
                pos=(text_leftpos[0], text_leftpos[1]),
                text="B: {} ({})".format(blackwinrate_text, bestmove_text),
                color=Theme.WHITE_STONE_COLOR.get(),
                font_size=self.height//1.5)

class EngineInfoPanelWidget(BoxLayout, BackgroundColor, RectangleBorder):
    def __init__(self, **kwargs):
        super(EngineInfoPanelWidget, self).__init__(**kwargs)

    def redraw(self):
        group = "engine_color"
        self.canvas.remove_group(group)
        if self.engine.get_mode() != GameMode.PLAYING:
            return

        comp_color = comp_side_to_color(self.config.get("game")["comp"])
        with self.canvas:
            stone_colors = Theme.STONE_COLORS
            outline_colors = Theme.OUTLINE_COLORS
            pos = (
                self.pos[0] + self.width/2.0,
                self.pos[1] + (self.height * 0.9)/2.0
            )
            stone_size = min(self.width, self.width)/8.0
            draw_circle(
                pos,
                stone_size,
                stone_colors[comp_color].get(),
                outline_color=outline_colors[comp_color].get(),
                group=group
            )

    def update_info(self):
        if self.engine.valid():
            name = "Sayuri"
            if self.engine.get_mode() == GameMode.ANALYZING:
                name += " (analyzing...)"
            elif self.engine.get_mode() == GameMode.PLAYING:
                name += " (playing)"
            self.name_label.text = name
            self.redraw()
        else:
            self.name_label.text = "NA"

class PlayerInfoPanelWidget(BoxLayout, BackgroundColor, RectangleBorder):
    def __init__(self, **kwargs):
        super(PlayerInfoPanelWidget, self).__init__(**kwargs)

    def redraw(self):
        group = "engine_color"
        self.canvas.remove_group(group)
        if self.engine.get_mode() != GameMode.PLAYING:
            return

        comp_color = comp_side_to_color(self.config.get("game")["comp"])
        player_color = [Board.WHITE, Board.BLACK, Board.EMPTY, Board.INVLD][comp_color]
        with self.canvas:
            stone_colors = Theme.STONE_COLORS
            outline_colors = Theme.OUTLINE_COLORS
            pos = (
                self.pos[0] + self.width/2.0,
                self.pos[1] + (self.height * 0.9)/2.0
            )
            stone_size = min(self.width, self.width)/8.0
            draw_circle(
                pos,
                stone_size,
                stone_colors[player_color].get(),
                outline_color=outline_colors[player_color].get(),
                group=group
            )

    def update_info(self):
        if self.engine.valid():
            self.redraw()

class EngineControls:
    def __init__(self, parent):
        self.parent = parent
        self.engine = None

        command = self._get_command()
        try:
            if not command is None:
                self.engine = GtpEngine(command)
        except Exception:
            self.engine = None
        self._check_engine()

        self.last_rep_command = str()
        self.last_rep = str()
        self.sync_engine_state()
        self._bind()

    def _bind(self):
        Window.bind(on_request_close=self.on_request_close)

    def _get_command(self):
        engine_setting = DefaultConfig.get("engine")

        path = engine_setting.get("path", "")
        weights = engine_setting.get("weights", "")
        threads = engine_setting.get("threads", 1)
        if not engine_setting.get("load") or \
               len(path) == 0 or \
               len(weights) == 0:
            return None

        cmd = str()
        cmd += "{}".format(path)
        cmd += " -w {}".format(weights)
        cmd += " -t {}".format(threads)
        if engine_setting.get("use_optimistic", True):
            cmd += " --use-optimistic-policy"
        return cmd

    def _check_engine(self):
        if not self.engine:
            return
        name = self.engine.name()
        if name.lower() != "sayuri":
            self.engine.quit()
            self.engine.shutdown()
            self.engine = None
            sys.stderr.write("Must be Sayuri engine.\n")
            sys.stderr.flush()

    def valid(self):
        return not self.engine is None

    def get_mode(self):
        return self.parent.mode

    def is_waiting_gtp_response(self):
        return self.engine.get_remaining_queries() > 0

    def sync_engine_state(self):
        if not self.engine:
            return
        board = self.parent.board
        self.analyzing = False
        self.engine.send_command("clear_board")
        self.engine.send_command("boardsize {}".format(board.board_size))
        self.engine.send_command("komi {}".format(board.komi))

        if board.scoring_rule == Board.SCORING_TERRITORY:
            self.engine.send_command("sayuri-setoption name scoring rule value {}".format("territory"))
        elif board.scoring_rule == Board.SCORING_AREA:
            self.engine.send_command("sayuri-setoption name scoring rule value {}".format("area"))

        leaf_tag = self.parent.tree.get_tag()
        curr = self.parent.tree.root
        while leaf_tag != curr.get_tag():
            curr = curr.default
            col, vtx = curr.get_key().unpack()
            self.do_action(
                { "action" : "play", "color" : col, "vertex" : vtx }
            )

    def do_action(self, action):
        if not self.engine:
            return

        if action["action"] == "play":
            col = action["color"]
            vtx = action["vertex"]
            gtp_command = "play {} {}".format(col, vtx)
        elif action["action"] == "undo":
            gtp_command = "undo"
        elif action["action"] == "analyze":
            col = action["color"]
            ownership = self.parent.config.get("engine")["use_ownership"]
            gtp_command = "sayuri-analyze {} {} ownership {}".format(
                              col, 50, ownership)
            self.analyzing = True
        elif action["action"] == "stop-analyze":
            gtp_command = "protocol_version"
        elif action["action"] == "genmove":
            col = action["color"]
            gtp_command = "sayuri-genmove_analyze {} playouts {}".format(
                              col, 1600)
            self.analyzing = True
        else:
            return

        self.engine.send_command(gtp_command)
        if action["action"] == "analyze":
            time.sleep(0.05)

    def handle_gtp_result(self):
        if not self.engine:
            return

        while not self.engine.query_empty():
            q = self.engine.get_last_query()
            self.last_rep_command = q.get_main_command()
            self.last_rep = q.get_response()

        last_line = None
        playmove = None
        while not self.engine.analysis_empty():
            line = self.engine.get_analysis_line()
            if line["type"] == "end":
                self.analyzing = False
            elif line["type"] == "play":
                playmove = GtpVertex(line["data"].split()[-1])
            else:
                last_line = line

        if playmove and \
               self.parent.mode == GameMode.PLAYING:
            self.parent.tree.get_val()["move"] = playmove
            self.parent.tree.update_tag()

        if self.analyzing and last_line:
            self.parent.tree.get_val()["analysis"] = AnalysisParser(last_line["data"])
            self.parent.tree.update_tag()
            if self.parent.mode == GameMode.IDLE:
                self.parent.engine.do_action({ "action" : "stop-analyze" })

        if not self.analyzing and \
               self.parent.mode == GameMode.ANALYZING and \
               not "analyze" in self.last_rep_command:
            col = self.parent.board.get_gtp_color(self.parent.board.to_move)
            self.parent.engine.do_action({ "action" : "analyze", "color" : col })

    def on_request_close(self, *args, source=None):
        if not self.engine:
            return
        if self.analyzing:
            self.parent.engine.do_action({ "action" : "stop-analyze" })
        self.engine.quit()
        self.engine.shutdown()

class GamePanelWidget(BoxLayout, BackgroundColor, Screen):
    board = ObjectProperty(None)
    tree = ObjectProperty(None)
    engine = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(GamePanelWidget, self).__init__(**kwargs)
        self.board = Board(
            DefaultConfig.get("game")["size"],
            DefaultConfig.get("game")["komi"],
            DefaultConfig.get("game")["rule"])
        self.tree = Tree({ "board" : self.board.copy() })
        self.mode = GameMode.IDLE
        self.mode_temp = None

        self.engine = EngineControls(self)
        self._bind()
        self.event = Clock.schedule_interval(self._loop, 0.025)

    def _loop(self, *args):
        # When we leave the current page, all computational activities, including
        # analysis, must stop. We'll then save the current mode and resume its
        # execution once we return to this page.
        if self.manager.current != "game" and \
               self.mode != GameMode.IDLE:
            self.mode_temp = self.mode
            self.change_mode(GameMode.IDLE)
            return

        self.board_panel.draw_board_contents()
        if self.mode == GameMode.PLAYING:
            self.board_panel.handle_engine_move()
        self.engine.handle_gtp_result()
        self.engine_info_panel.update_info()
        self.player_info_panel.update_info()
        self.controls_panel.update_info()
        self.graph_info_panel.update_graph(self.tree)

    def change_mode(self, m, condition=None):
        if not m in GameMode:
            return False
        if not condition is None:
            if isinstance(condition, GameMode) and \
                   self.mode != condition:
                return False
            if isinstance(condition, list) and \
                   not self.mode in condition:
                return False
        self.mode = m
        return True

    def recover_mode(self):
        if self.config.get("game")["comp"].lower() != "na":
            self.change_mode(GameMode.PLAYING)
        elif not self.mode_temp is None:
            self.change_mode(self.mode_temp, GameMode.IDLE)
        self.mode_temp = None

    def load_sgf(self, sgf):
        try:
            self.tree.copy_from(sgf_parser.load_sgf_as_tree(sgf, True))
            self.board.copy_from(self.tree.get_val()["board"])
            self.config.get("game")["size"] = self.board.board_size
            self.config.get("game")["komi"] = self.board.komi
            self.config.get("game")["rule"] = ["chinese", "japanese"][self.board.scoring_rule]
            self.config.get("game")["comp"] = "NA"
            self.board_panel.on_size() # redraw
            self.engine.sync_engine_state()
        except Exception:
            pass

    def sync_config_and_reset(self):
        self.board.reset(
            self.config.get("game")["size"],
            self.config.get("game")["komi"],
            self.config.get("game")["rule"])
        self.tree.reset({ "board" : self.board.copy() })
        self.board_panel.on_size() # redraw
        self.engine.sync_engine_state()

    def _bind(self):
        self.keyboard = Window.request_keyboard(None, self, "")
        self.keyboard.bind(on_key_down=self.on_keyboard_down)

    def on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if self.manager.current == "game" and \
               (keycode[1] == "a" or keycode[1] == "spacebar"):
            # ANALYZING <-> IDLE
            if self.change_mode(GameMode.ANALYZING, GameMode.IDLE) or \
                   self.change_mode(GameMode.IDLE, GameMode.ANALYZING):
                pass

            # ANALYZING <- PLAYING
            if not self.engine.is_waiting_gtp_response() and \
                   self.change_mode(GameMode.ANALYZING, GameMode.PLAYING):
                self.config.get("game")["comp"] = "NA"
        return True

class GameAnalysisWidget(BoxLayout, BackgroundColor, Screen):
    def __init__(self, **kwargs):
        super(GameAnalysisWidget, self).__init__(**kwargs)

    def sync_config(self):
        self.show_bar.elem_label.text = self.config.get("engine")["show"]
        self.pv_bar.elem_label.text = str(self.config.get("engine")["pv"])
        self.ownership_bar.elem_label.text = str(self.config.get("engine")["use_ownership"])

        all_bars = [
            self.show_bar,
            self.pv_bar,
            self.ownership_bar
        ]
        for bar in all_bars:
            elemidx = 0
            for idx in range(len(bar.elemset)):
                if bar.elemset[idx] == bar.elem_label.text:
                    elemidx = idx
                    break
            bar.elem_label.text = bar.elemset[elemidx]
            bar.elemidx = elemidx

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"
        self.manager.get_screen(self.manager.current).canvas.ask_update()
        self.manager.get_screen(self.manager.current).recover_mode()

    def confirm_and_back(self):
        self.config.get("engine")["show"] = self.show_bar.elem_label.text
        self.config.get("engine")["pv"] = self._text_to_bool(self.pv_bar.elem_label.text)
        self.config.get("engine")["use_ownership"] = \
            self._text_to_bool(self.ownership_bar.elem_label.text)
        self.manager.get_screen("game").engine.do_action(
            { "action" : "stop-analyze" }
        )
        self.back_only()

    def _text_to_bool(self, text):
        return text.lower() == "true"

class GameSettingWidget(BoxLayout, BackgroundColor, Screen):
    def __init__(self, **kwargs):
        super(GameSettingWidget, self).__init__(**kwargs)

    def sync_config(self):
        self.comp_side_bar.elem_label.text = str(self.config.get("game")["comp"])
        self.board_size_bar.value_label.text = str(self.config.get("game")["size"])
        self.komi_bar.value_label.text = str(self.config.get("game")["komi"])

        scoring_rule = self.config.get("game")["rule"].lower()
        if scoring_rule in ["japanese", "territory", "jp"]:
            self.rule_bar.elem_label.text = "JP"
        elif scoring_rule in ["chinese", "area", "cn"]:
            self.rule_bar.elem_label.text = "CN"

        all_bars = [
            self.comp_side_bar,
            self.rule_bar
        ]
        for bar in all_bars:
            elemidx = 0
            for idx in range(len(bar.elemset)):
                if bar.elemset[idx] == bar.elem_label.text:
                    elemidx = idx
                    break
            bar.elem_label.text = bar.elemset[elemidx]
            bar.elemidx = elemidx

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"
        self.manager.get_screen(self.manager.current).canvas.ask_update()
        self.manager.get_screen(self.manager.current).recover_mode()

    def confirm_and_back(self):
        self.config.get("game")["comp"] = self.comp_side_bar.elem_label.text
        self.config.get("game")["size"] = int(self.board_size_bar.value_label.text)
        self.config.get("game")["komi"] = float(self.komi_bar.value_label.text)
        self.config.get("game")["rule"] = self.rule_bar.elem_label.text
        self.manager.get_screen("game").sync_config_and_reset()
        self.back_only()

class GameIOWidget(BoxLayout, BackgroundColor, Screen):
    board = Board(19, 7.5, Board.SCORING_AREA)

    def __init__(self, **kwargs):
        super(GameIOWidget, self).__init__(**kwargs)
        self.source = str()

    def update_view_board(self, path):
        self.source = path[0]
        try:
            with open(self.source, "r") as f:
                sgf = f.read()
            self.board.copy_from(sgf_parser.load_sgf_as_board(sgf, True))
            self.simple_board_panel.on_size()
        except Exception:
            self.source = str()

    def load(self):
        try:
            with open(self.source, "r") as f:
                sgf = f.read()
        except Exception:
            sgf = None
        self.manager.transition.direction = "left"
        self.manager.current = "game"
        if not sgf is None:
            self.manager.get_screen(self.manager.current).load_sgf(sgf)
        self.manager.get_screen(self.manager.current).canvas.ask_update()

    def back_only(self):
        self.manager.transition.direction = "left"
        self.manager.current = "game"
        self.manager.get_screen(self.manager.current).canvas.ask_update()

class WindowApp(App):
    def build(self):
        self.title = "Go GUI"
        Window.size = (1200, 900)

        self.config = DefaultConfig
        replace_theme(self.config.get("theme"))

        self.manager = ScreenManager()
        self.manager.add_widget(GamePanelWidget(name="game"))
        self.manager.add_widget(GameSettingWidget(name="game-setting"))
        self.manager.add_widget(GameAnalysisWidget(name="game-analysis"))
        self.manager.add_widget(GameIOWidget(name="game-io"))
        self.manager.current = "game"
        return self.manager

def run_app():
    kv_file = "widgets.kv"
    resource_add_path(kv_file)
    Builder.load_file(kv_file)
    app = WindowApp()
    app.run()
