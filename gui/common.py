from kivy.uix.widget import Widget
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Rectangle, Line, Ellipse, Color
from enum import Enum

class GameMode(Enum):
    IDLE = 0
    ANALYZING = 1
    PLAYING = 2

class BackgroundColor(Widget):
    pass

class RectangleBorder(Widget):
    pass

def draw_text(pos, text, color, **kwargs):
    _kwargs = kwargs.copy()
    group = _kwargs.pop("group", None)

    Color(*color)
    label = CoreLabel(text=text, halign="center", valign="middle", bold=True, **_kwargs)
    label.refresh()
    Rectangle(
        texture=label.texture,
        pos=(pos[0] - label.texture.size[0] / 2, pos[1] - label.texture.size[1] / 2),
        size=label.texture.size,
        group=group)

def draw_circle(pos, stone_size, color=None, **kwargs):
    _kwargs = kwargs.copy()
    outline_color = _kwargs.pop("outline_color", None)
    scale = _kwargs.pop("scale", 1.0)
    outline_scale = _kwargs.pop("outline_scale", 0.065)
    outline_align = _kwargs.pop("outline_align", "outer")
    group = _kwargs.pop("group", None)
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