from kivy.core.window import Window
from kivy.storage.jsonstore import JsonStore
import time

from .common import GameMode

from game.gtp import GtpEngine, GtpVertex
from game.board import Board
from game.analysis import AnalysisParser

DefaultConfig = JsonStore("config.json")

class EngineControls:
    def __init__(self, parent, default_config):
        self.parent = parent
        self.engine = None

        command = self._get_command(default_config.get("engine"))
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

    def _get_command(self, engine_setting):
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
        if not self.engine:
            return False
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
            scoring = "territory"
        elif board.scoring_rule == Board.SCORING_AREA:
            scoring = "area"
        else:
            scoring = None
        self.engine.send_command(
                "sayuri-setoption name scoring rule value {}".format(scoring))

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