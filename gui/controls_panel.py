from kivy.uix.boxlayout import BoxLayout
from .common import BackgroundColor

from game.board import Board
from game.gtp import GtpVertex
from game.tree import NodeKey

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