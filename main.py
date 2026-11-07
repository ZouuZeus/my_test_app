"""Kivy screen for the code calculator.

The calculation itself lives in codegen.py (your original script, renamed
from main.py). This file only adds the phone screen around it and does not
change any of the maths.
"""
from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# Keep the focused text box visible when the on-screen keyboard opens.
Window.softinput_mode = "below_target"

# If the original script is missing or broken, show the reason on screen
# instead of closing the app.
try:
    import codegen
    IMPORT_ERROR = None
except Exception as exc:
    codegen = None
    IMPORT_ERROR = "{}: {}".format(type(exc).__name__, exc)

AUTO = "Auto"
ERROR_COLOR = (1, 0.35, 0.35, 1)
NORMAL_COLOR = (1, 1, 1, 1)


def wrapped_label(text="", font_size=sp(16), **kwargs):
    """Label that wraps to its width and grows to fit its text."""
    label = Label(
        text=text,
        font_size=font_size,
        size_hint_y=None,
        halign="center",
        valign="middle",
        **kwargs
    )
    label.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    label.bind(
        texture_size=lambda inst, size: setattr(inst, "height", max(size[1], dp(32)))
    )
    return label


class CalculatorScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical", padding=dp(16), spacing=dp(12), **kwargs
        )

        self.add_widget(
            wrapped_label("Code Calculator", font_size=sp(24), bold=True)
        )

        self.device_input = TextInput(
            hint_text="Device number",
            multiline=False,
            write_tab=False,
            size_hint_y=None,
            height=dp(52),
            font_size=sp(18),
        )
        self.add_widget(self.device_input)

        self.usage_input = TextInput(
            hint_text="Usage count",
            multiline=False,
            write_tab=False,
            input_filter="int",
            input_type="number",
            size_hint_y=None,
            height=dp(52),
            font_size=sp(18),
        )
        self.add_widget(self.usage_input)

        families = getattr(codegen, "FAMILY_TABLE", None)
        names = list(families.keys()) if isinstance(families, dict) else []
        self.family_spinner = Spinner(
            text=AUTO,
            values=[AUTO] + [str(name) for name in names],
            size_hint_y=None,
            height=dp(52),
            font_size=sp(18),
        )
        self.add_widget(self.family_spinner)

        calc_button = Button(
            text="Calculate",
            size_hint_y=None,
            height=dp(56),
            font_size=sp(20),
        )
        calc_button.bind(on_release=self.calculate)
        self.add_widget(calc_button)

        self.result_label = wrapped_label("", font_size=sp(28), bold=True)
        self.add_widget(self.result_label)

        self.copy_button = Button(
            text="Copy code",
            size_hint_y=None,
            height=dp(48),
            font_size=sp(18),
            disabled=True,
        )
        self.copy_button.bind(on_release=self.copy_code)
        self.add_widget(self.copy_button)

        self.status_label = wrapped_label("", font_size=sp(15))
        self.add_widget(self.status_label)

        # Soaks up the leftover space so everything stays at the top.
        self.add_widget(Widget())

        if IMPORT_ERROR:
            self.show_error("Could not load codegen.py - " + IMPORT_ERROR)
            calc_button.disabled = True

    def show_error(self, message):
        self.result_label.text = ""
        self.copy_button.disabled = True
        self.status_label.color = ERROR_COLOR
        self.status_label.text = message

    def calculate(self, *_):
        device = self.device_input.text.strip()
        usage_text = self.usage_input.text.strip()

        if not device:
            self.show_error("Enter the device number.")
            return
        if not usage_text:
            self.show_error("Enter the usage count.")
            return
        try:
            usage = int(usage_text)
        except ValueError:
            self.show_error("Usage count must be a whole number.")
            return

        family = None if self.family_spinner.text == AUTO else self.family_spinner.text

        try:
            code = codegen.compute_twelve_digit_code(device, usage, family=family)
        except Exception as exc:
            self.show_error("Calculation failed: {}: {}".format(type(exc).__name__, exc))
            return

        self.result_label.text = str(code)
        self.copy_button.disabled = False
        self.status_label.color = NORMAL_COLOR
        self.status_label.text = ""

    def copy_code(self, *_):
        if self.result_label.text:
            Clipboard.copy(self.result_label.text)
            self.status_label.color = NORMAL_COLOR
            self.status_label.text = "Copied."


class CodeCalculatorApp(App):
    title = "Code Calculator"

    def build(self):
        return CalculatorScreen()


if __name__ == "__main__":
    CodeCalculatorApp().run()
