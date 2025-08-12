from kivy.uix.boxlayout import BoxLayout
from .common import BackgroundColor

class MenuPanelWidget(BoxLayout, BackgroundColor):
    def __init__(self, **kwargs):
        super(MenuPanelWidget, self).__init__(**kwargs)

    def switch_to_gameio(self):
        self.manager.transition.direction = "right"
        self.manager.current = "game-io"
        self.manager.get_screen("game-io").canvas.ask_update()