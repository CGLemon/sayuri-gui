from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Rectangle, Color

from .common import BackgroundColor, RectangleBorder
from .common import draw_text
from .common import GameMode

from theme import Theme

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
            bestmove = None if info is None else info["move"]
            bestpolicy = 0.0 if info is None else info["prior"]
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
        blackscore_text = "{:3.1f}".format(0.0)
        bestpolicy_text = "{:3.1f}%".format(0.0 * 100.0)
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

            margin = 0.25
            text_leftpos = [
                self.pos[0] + self.width * margin/2.0,
                self.pos[1] + self.height/2.0
            ]
            text_rightpos = [
                self.pos[0] + self.width * (1.0 - margin/2.0),
                self.pos[1] + self.height/2.0
            ]
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
                blackwinrate_text = "{:3.1f}%".format(blackwinrate * 100.0)
                blackscore_text = "{:3.1f}".format(stats["blackscore"])
                bestpolicy_text = "{:3.1f}%".format(stats["bestpolicy"] * 100.0)
                bestmove_text = str(stats["bestmove"])
            draw_text(
                pos=(text_leftpos[0], text_leftpos[1]),
                text="B: {} ({})".format(blackwinrate_text, blackscore_text),
                color=Theme.WHITE_STONE_COLOR.get(),
                font_size=self.height//1.5)
            draw_text(
                pos=(text_rightpos[0], text_rightpos[1]),
                text="Best: {} ({})".format(bestmove_text, bestpolicy_text),
                color=Theme.WHITE_STONE_COLOR.get(),
                font_size=self.height//1.5)