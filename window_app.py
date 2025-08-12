import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen

from kivy.properties import ObjectProperty
from kivy.lang import Builder
from kivy.resources import resource_add_path
from kivy.core.window import Window
# from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.storage.jsonstore import JsonStore

from game.tree import Tree, NodeKey
from game.board import Board
from game.gtp import GtpEngine, GtpVertex
from game.analysis import AnalysisParser
import game.sgf_parser as sgf_parser

from gui.common import BackgroundColor, RectangleBorder
from gui.common import draw_text, draw_circle
from gui.common import GameMode
from gui.board_panel import SimpleBoardPanelWidget, BoardPanelWidget
from gui.menu_panel import MenuPanelWidget
from gui.controls_panel import ControlsPanelWidget
from gui.graph_panel import GraphPanelWidget
from gui.info_panel import EngineInfoPanelWidget, PlayerInfoPanelWidget
from gui.engine import EngineControls

from theme import Theme, replace_theme
import sys, time
from enum import Enum

kivy.config.Config.set("input", "mouse", "mouse,multitouch_on_demand")
DefaultConfig = JsonStore("config.json")

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

        self.engine = EngineControls(self, DefaultConfig)
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

            # PLAYING -> ANALYZING
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
        self.title = "Sayuri"
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
