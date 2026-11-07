"""Kivy screen for the code calculator.

The calculation itself lives in codegen.py (your original script, renamed
from main.py). This file only adds the phone screen around it and does not
change any of the maths.
"""
import random
import traceback

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# If the original script is missing or broken, show the reason on screen
# instead of closing the app.
try:
    import codegen
    IMPORT_ERROR = None
except Exception as exc:
    codegen = None
    IMPORT_ERROR = "{}: {}".format(type(exc).__name__, exc)


def hex_color(value, alpha=1.0):
    value = value.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, alpha)


# ---- Palette -------------------------------------------------------------
BG = hex_color("#0d1017")
SURFACE = hex_color("#171b26")
BORDER = hex_color("#272d3d")
TEXT = hex_color("#f2f4f8")
MUTED = hex_color("#8b93a7")
ACCENT = hex_color("#7357ff")
ACCENT_PRESSED = hex_color("#5e44e0")
ACCENT_SOFT = hex_color("#a99bff")
ACCENT_TINT = hex_color("#7357ff", 0.18)
SELECTION = hex_color("#7357ff", 0.35)
ERROR = hex_color("#ff6b6b")
DISABLED_FILL = hex_color("#2a2f40")
TRANSPARENT = (0, 0, 0, 0)

# Background animation: faint glow + bright core of each electric thread.
THREAD_GLOW = ACCENT
THREAD_CORE = hex_color("#cfc6ff")
THREAD_COUNT = 4
THREAD_GLOW_ALPHA = 0.18
THREAD_CORE_ALPHA = 0.6
THREAD_GLOW_WIDTH = 5     # in dp
THREAD_CORE_WIDTH = 1.4   # in dp

# Shown at the bottom of the screen; tapping it opens the profile.
INSTAGRAM_HANDLE = "@zeus__hz"
INSTAGRAM_URL = "https://www.instagram.com/" + INSTAGRAM_HANDLE.lstrip("@") + "/"

Window.clearcolor = BG
# Keep the focused text box visible when the on-screen keyboard opens.
Window.softinput_mode = "below_target"


# ---- Logic (no screen code here) ----------------------------------------
def make_code(device_text, usage_text):
    """Validate the two inputs and return (code, error_message).

    The code comes back with every space removed.
    """
    device = device_text.strip()
    usage_text = usage_text.strip()

    if not device:
        return None, "Enter the device number."
    if not usage_text:
        return None, "Enter the usage count."
    try:
        usage = int(usage_text)
    except ValueError:
        return None, "Usage count must be a whole number."

    try:
        code = codegen.compute_twelve_digit_code(device, usage)
    except Exception as exc:
        return None, "Calculation failed: {}: {}".format(type(exc).__name__, exc)

    return "".join(str(code).split()), None


def open_url(url):
    """Open a link on the phone (Instagram app or browser). True if it worked."""
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        intent_class = autoclass("android.content.Intent")
        uri = autoclass("android.net.Uri").parse(url)
        activity.startActivity(intent_class(intent_class.ACTION_VIEW, uri))
        return True
    except Exception:
        pass
    try:
        import webbrowser

        return bool(webbrowser.open(url))
    except Exception:
        return False


def set_immersive(*_):
    """Draw edge to edge: under the status bar, nav bar and camera cutout."""
    try:
        from android.runnables import run_on_ui_thread
        from jnius import autoclass

        @run_on_ui_thread
        def _apply():
            try:
                VERSION = autoclass("android.os.Build$VERSION")
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                window = activity.getWindow()

                # Draw into the notch / camera cutout area
                params = window.getAttributes()
                params.layoutInDisplayCutoutMode = (
                    3 if VERSION.SDK_INT >= 30 else 1
                )
                window.setAttributes(params)

                # Let the window extend beyond the screen limits, transparent bars
                window.addFlags(0x00000200)  # FLAG_LAYOUT_NO_LIMITS
                window.setStatusBarColor(0)
                window.setNavigationBarColor(0)

                window.getDecorView().setSystemUiVisibility(
                    0x00000100 | 0x00000200 | 0x00000400  # layout under bars
                    | 0x00000002 | 0x00000004             # hide nav + status
                    | 0x00001000                          # sticky immersive
                )
            except Exception:
                print("IMMERSIVE ERROR:", traceback.format_exc())

        _apply()
    except Exception:
        # Not running on Android (or android module missing): nothing to do.
        print("IMMERSIVE ERROR:", traceback.format_exc())


# ---- Small building blocks ----------------------------------------------
def spacer(height):
    return Widget(size_hint_y=None, height=dp(height))


def text_label(text="", size=16, color=TEXT, bold=False, min_height=0,
               halign="left"):
    """Label that wraps to its width and grows to fit its text."""
    label = Label(
        text=text,
        font_size=sp(size),
        color=color,
        bold=bold,
        halign=halign,
        valign="middle",
        size_hint_y=None,
    )
    label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    label.bind(
        texture_size=lambda inst, ts: setattr(inst, "height", max(ts[1], min_height))
    )
    return label


class RoundedBox(BoxLayout):
    """BoxLayout with a rounded, outlined background."""

    def __init__(self, fill=SURFACE, border=BORDER, radius=16, **kwargs):
        super().__init__(**kwargs)
        self._radius = dp(radius)
        with self.canvas.before:
            Color(*fill)
            self._fill = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
            self._border_color = Color(*border)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius),
                width=dp(1.2),
            )
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self._fill.pos = self.pos
        self._fill.size = self.size
        self._border.rounded_rectangle = (
            self.x, self.y, self.width, self.height, self._radius
        )

    def set_border(self, color):
        self._border_color.rgba = color


class Field(RoundedBox):
    """Rounded text box that lights up with the accent colour when focused."""

    def __init__(self, hint, numeric=False, **kwargs):
        super().__init__(size_hint_y=None, height=dp(54), radius=14, **kwargs)
        options = {"input_filter": "int", "input_type": "number"} if numeric else {}
        self.input = TextInput(
            hint_text=hint,
            multiline=False,
            write_tab=False,
            background_normal="",
            background_active="",
            background_color=TRANSPARENT,
            foreground_color=TEXT,
            hint_text_color=MUTED,
            cursor_color=ACCENT,
            selection_color=SELECTION,
            font_size=sp(18),
            **options
        )
        self.add_widget(self.input)
        self.input.bind(
            focus=self._on_focus,
            height=self._center_text,
            line_height=self._center_text,
        )

    @property
    def text(self):
        return self.input.text

    def _on_focus(self, _inst, focused):
        self.set_border(ACCENT if focused else BORDER)

    def _center_text(self, *_):
        pad_y = max(0, (self.input.height - self.input.line_height) / 2)
        self.input.padding = [dp(16), pad_y, dp(16), 0]


class RoundedButton(Button):
    """Flat rounded button with its own pressed and disabled colours."""

    def __init__(self, fill, pressed_fill, border=None, text_color=TEXT,
                 radius=16, **kwargs):
        super().__init__(
            background_normal="",
            background_down="",
            background_disabled_normal="",
            background_disabled_down="",
            background_color=TRANSPARENT,
            color=text_color,
            disabled_color=MUTED,
            bold=True,
            **kwargs
        )
        self._normal = fill
        self._pressed = pressed_fill
        self._radius = dp(radius)
        with self.canvas.before:
            self._fill_color = Color(*fill)
            self._fill = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[self._radius]
            )
            Color(*(border or TRANSPARENT))
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, self._radius),
                width=dp(1.2),
            )
        self.bind(
            pos=self._redraw, size=self._redraw,
            state=self._recolor, disabled=self._recolor,
        )

    def _redraw(self, *_):
        self._fill.pos = self.pos
        self._fill.size = self.size
        self._border.rounded_rectangle = (
            self.x, self.y, self.width, self.height, self._radius
        )

    def _recolor(self, *_):
        if self.disabled:
            self._fill_color.rgba = DISABLED_FILL
        elif self.state == "down":
            self._fill_color.rgba = self._pressed
        else:
            self._fill_color.rgba = self._normal


# ---- Background animation: fading electric threads ----------------------
class ThreadModel:
    """One crackling thread: its shape, and how bright it is right now.

    Plain Python (no Kivy), so it can be tested without a phone.
    Coordinates are in dp, with (0, 0) at the bottom-left of the widget.
    """

    def __init__(self, rng, width, height, delay=0.0):
        self.rng = rng
        self.width = float(width)
        self.height = float(height)
        self.life = 1.0
        self.age = 0.0
        self.paths = []
        self._spawn()
        self.age = -delay

    def _spawn(self):
        rng, w, h = self.rng, self.width, self.height
        self.life = rng.uniform(1.5, 2.8)
        self.age = -rng.uniform(0.0, 0.9)  # short pause before the next flash

        steps = rng.randint(14, 22)
        x = rng.uniform(0.1, 0.9) * w
        y = h * rng.uniform(0.75, 1.0)
        step_y = h * rng.uniform(0.45, 0.8) / steps
        main = [x, y]
        for _ in range(steps):
            x = min(max(x + rng.uniform(-1.0, 1.0) * w * 0.07, 0.0), w)
            y = max(y - step_y * rng.uniform(0.6, 1.4), 0.0)
            main += [x, y]
        self.paths = [main]

        if rng.random() < 0.6:  # a smaller branch splitting off the main thread
            i = rng.randrange(3, steps - 3)
            bx, by = main[2 * i], main[2 * i + 1]
            side = rng.choice((-1.0, 1.0))
            branch = [bx, by]
            for _ in range(rng.randint(5, 9)):
                bx = min(max(bx + side * rng.uniform(0.2, 1.0) * w * 0.05, 0.0), w)
                by = max(by - step_y * rng.uniform(0.5, 1.2), 0.0)
                branch += [bx, by]
            self.paths.append(branch)

    @property
    def brightness(self):
        """0 to 1: a quick flash in, then a slow fade out."""
        p = self.age / self.life
        if p <= 0.0 or p >= 1.0:
            return 0.0
        if p < 0.12:
            return p / 0.12
        return ((1.0 - p) / 0.88) ** 1.6

    def advance(self, dt):
        self.age += dt
        if self.age >= self.life:
            self._spawn()

    def shimmer(self):
        """The current shape, nudged a little so the thread seems to crackle."""
        amount = max(self.width, 1.0) * 0.006
        uniform = self.rng.uniform
        return [[v + uniform(-amount, amount) for v in path] for path in self.paths]


class ThreadSlot:
    """The drawing instructions (glow line + bright core line) for one path."""

    def __init__(self, canvas):
        with canvas:
            self.glow_color = Color(*THREAD_GLOW[:3], 0)
            self.glow = Line(points=[], width=dp(THREAD_GLOW_WIDTH), cap="none")
            self.core_color = Color(*THREAD_CORE[:3], 0)
            self.core = Line(points=[], width=dp(THREAD_CORE_WIDTH), cap="none")

    def show(self, points, level):
        self.glow_color.rgba = (*THREAD_GLOW[:3], level * THREAD_GLOW_ALPHA)
        self.core_color.rgba = (*THREAD_CORE[:3], level * THREAD_CORE_ALPHA)
        self.glow.points = points
        self.core.points = points

    def hide(self):
        self.glow_color.rgba = (*THREAD_GLOW[:3], 0)
        self.core_color.rgba = (*THREAD_CORE[:3], 0)
        self.glow.points = []
        self.core.points = []


class ElectricThreads(Widget):
    """Fading electric threads, drawn behind the rest of the screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rng = random.Random()
        self._items = []  # (ThreadModel, [ThreadSlot, ThreadSlot])
        self.bind(size=self._rebuild)
        self._timer = Clock.schedule_interval(self._tick, 1.0 / 30.0)

    def _rebuild(self, *_):
        self.canvas.clear()
        self._items = []
        if self.width < 2 or self.height < 2:
            return
        for i in range(THREAD_COUNT):
            model = ThreadModel(self._rng, self.width, self.height, delay=i * 0.55)
            slots = [ThreadSlot(self.canvas), ThreadSlot(self.canvas)]
            self._items.append((model, slots))

    def _tick(self, dt):
        # This is only decoration: if anything goes wrong, stop it quietly
        # rather than taking the whole app down.
        try:
            dt = min(dt, 0.1)
            ox, oy = self.x, self.y
            for model, slots in self._items:
                model.advance(dt)
                level = model.brightness
                if level <= 0.0:
                    for slot in slots:
                        slot.hide()
                    continue
                level *= 0.8 + 0.2 * self._rng.random()  # slight flicker
                paths = model.shimmer()
                for index, slot in enumerate(slots):
                    if index < len(paths):
                        points = [v + (ox if n % 2 == 0 else oy)
                                  for n, v in enumerate(paths[index])]
                        slot.show(points, level)
                    else:
                        slot.hide()
        except Exception:
            self._timer.cancel()
            self.canvas.clear()


# ---- The screen ------------------------------------------------------------
class CalculatorScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=[dp(20), dp(44), dp(20), dp(16)],
            spacing=0,
            **kwargs
        )

        # Header
        badge_row = BoxLayout(size_hint_y=None, height=dp(46))
        badge = RoundedBox(
            fill=ACCENT, border=ACCENT, radius=14,
            size_hint=(None, None), size=(dp(46), dp(46)),
        )
        badge.add_widget(Label(text="#", font_size=sp(24), bold=True, color=TEXT))
        badge_row.add_widget(badge)
        badge_row.add_widget(Widget())
        self.add_widget(badge_row)
        self.add_widget(spacer(16))
        self.add_widget(text_label("Shazam mf!!", size=27, bold=True))
        self.add_widget(spacer(6))
        self.add_widget(
            text_label("Enter the device details to generate a code.",
                       size=14, color=MUTED)
        )
        self.add_widget(spacer(24))

        # Inputs
        self.add_widget(text_label("DEVICE NUMBER", size=12, color=MUTED, bold=True))
        self.add_widget(spacer(8))
        self.device_field = Field("Device number")
        self.add_widget(self.device_field)
        self.add_widget(spacer(16))
        self.add_widget(text_label("USAGE COUNT", size=12, color=MUTED, bold=True))
        self.add_widget(spacer(8))
        self.usage_field = Field("Usage count", numeric=True)
        self.add_widget(self.usage_field)
        self.add_widget(spacer(22))

        # Calculate
        self.calc_button = RoundedButton(
            fill=ACCENT, pressed_fill=ACCENT_PRESSED, radius=16,
            text="Calculate", font_size=sp(17),
            size_hint_y=None, height=dp(56),
        )
        self.calc_button.bind(on_release=self.calculate)
        self.add_widget(self.calc_button)
        self.add_widget(spacer(8))

        # Messages (errors show here)
        self.status_label = text_label("", size=15, color=ERROR)
        self.add_widget(self.status_label)
        self.add_widget(spacer(14))

        # Result card, hidden until there is a code
        self.card = RoundedBox(
            orientation="vertical", radius=20, size_hint_y=None, height=0,
            padding=[dp(18), dp(18), dp(18), dp(16)],
            opacity=0, disabled=True,
        )
        self.card.bind(minimum_height=self.card.setter("height"))
        self.card.add_widget(
            text_label("YOUR CODE", size=12, color=ACCENT_SOFT, bold=True)
        )
        self.card.add_widget(spacer(6))
        self.code_label = text_label("", size=31, bold=True)
        self.card.add_widget(self.code_label)
        self.card.add_widget(spacer(14))
        self.copy_button = RoundedButton(
            fill=TRANSPARENT, pressed_fill=ACCENT_TINT, border=ACCENT,
            text_color=ACCENT_SOFT, radius=13,
            text="Copy code", font_size=sp(16),
            size_hint_y=None, height=dp(46),
        )
        self.copy_button.bind(on_release=self.copy_code)
        self.card.add_widget(self.copy_button)
        self.add_widget(self.card)

        # Soaks up leftover space so everything stays at the top.
        self.add_widget(Widget())

        # Footer: tappable Instagram handle
        self.footer_button = Button(
            text=INSTAGRAM_HANDLE,
            font_size=sp(15),
            color=ACCENT_SOFT,
            background_normal="",
            background_down="",
            background_color=TRANSPARENT,
            size_hint_y=None,
            height=dp(44),
        )
        self.footer_button.bind(on_release=self.open_instagram)
        self.add_widget(self.footer_button)

        if IMPORT_ERROR:
            self.show_error("Could not load codegen.py - " + IMPORT_ERROR)
            self.calc_button.disabled = True

    def hide_card(self):
        Animation.cancel_all(self.card)
        self.card.opacity = 0
        self.card.disabled = True

    def show_card(self):
        Animation.cancel_all(self.card)
        self.card.opacity = 0
        self.card.disabled = False
        Animation(opacity=1, duration=0.4, t="out_quad").start(self.card)

    def show_error(self, message):
        self.hide_card()
        self.status_label.text = message

    def calculate(self, *_):
        self.device_field.input.focus = False
        self.usage_field.input.focus = False

        code, error = make_code(self.device_field.text, self.usage_field.text)
        if error:
            self.show_error(error)
            return

        self.status_label.text = ""
        self.code_label.text = code
        self.copy_button.text = "Copy code"
        self.show_card()

    def copy_code(self, *_):
        if not self.code_label.text:
            return
        Clipboard.copy(self.code_label.text)
        self.copy_button.text = "Copied"
        Clock.unschedule(self._reset_copy_text)
        Clock.schedule_once(self._reset_copy_text, 1.5)

    def _reset_copy_text(self, *_):
        self.copy_button.tex
