from kivy.uix.boxlayout import BoxLayout
from .common import BackgroundColor, RectangleBorder
from gui.common import draw_text, draw_circle
from .common import GameMode

from theme import Theme
from game.board import Board

def comp_side_to_color(comp_side):
    comp_color = None
    if comp_side.lower() == "na":
        comp_color = Board.INVLD
    elif comp_side.lower() == "b":
        comp_color = Board.BLACK
    elif comp_side.lower() == "w":
        comp_color = Board.WHITE
    return comp_color

class EngineInfoPanelWidget(BoxLayout, BackgroundColor, RectangleBorder):
    def __init__(self, **kwargs):
        super(EngineInfoPanelWidget, self).__init__(**kwargs)

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
                color=stone_colors[comp_color].get(),
                outline_color=outline_colors[comp_color].get(),
                group=group)
            draw_text(
                pos=pos,
                text="{}".format(self.board.prisoners[comp_color]),
                color=stone_colors[player_color].get(),
                font_size=stone_size,
                group=group)

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
        group = "player_color"
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
                group=group)
            draw_text(
                pos=pos,
                text="{}".format(self.board.prisoners[player_color]),
                color=stone_colors[comp_color].get(),
                font_size=stone_size,
                group=group)

    def update_info(self):
        if self.engine.valid():
            self.redraw()