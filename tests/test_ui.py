"""
Pruebas de la interfaz. Requieren Tk real: se omiten donde no está disponible
(p. ej. contenedores Linux sin tkinter) y corren en el runner de Windows de la CI.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

try:
    import tkinter
    _HAS_TK = not isinstance(tkinter, MagicMock)
except ImportError:
    _HAS_TK = False

pytestmark = pytest.mark.skipif(not _HAS_TK, reason="Tk no disponible")


@pytest.fixture(scope="module")
def tk_root():
    import ttkbootstrap as tb

    try:
        root = tb.Window(themename="vapor")
    except tkinter.TclError as exc:  # sin pantalla
        pytest.skip(f"No se pudo crear la ventana Tk: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(tk_root):
    from history import History

    app = MagicMock()
    app.root = tk_root
    app.history = History()
    # Ejecuta de inmediato lo programado (en los tests ya estamos en el hilo de Tk).
    app.schedule.side_effect = lambda cb, *args: cb(*args)
    return app


def _pump(root):
    for _ in range(5):
        root.update()


class TestPureHelpers:
    def test_group_by_section_keeps_order(self):
        from ui_menu import group_by_section

        actions = [{"section": "B", "label": "1"}, {"section": "A", "label": "2"},
                   {"section": "B", "label": "3"}]
        assert [(s, [a["label"] for a in acts]) for s, acts in group_by_section(actions)] == [
            ("B", ["1", "3"]), ("A", ["2"]),
        ]

    def test_button_text_shows_only_valid_shortcuts(self):
        from ui_menu import button_text

        assert button_text({"label": "X", "shortcut": "Ctrl+J", "shortcut_key": "<Control-j>"}).endswith("Ctrl+J")
        assert button_text({"label": "X", "shortcut": "malo", "shortcut_key": None}) == "X"


class TestResultWindow:
    def test_streaming_lifecycle(self, app):
        from ui_result import ResultWindow

        win = ResultWindow(app, "", 1234, prompt="p", selected_text="t", streaming=True)
        assert str(win._copy_btn["state"]) == "disabled"

        win.append_chunk("Hola ")
        win.append_chunk("mundo")
        assert win.text_widget.get("1.0", "end").strip() == "Hola mundo"

        win.finish("Hola mundo.", "gemini")
        assert win.text_widget.get("1.0", "end").strip() == "Hola mundo."
        assert str(win._copy_btn["state"]) == "normal"
        assert str(win._replace_btn["state"]) == "normal"
        win.window.destroy()

    def test_replace_disabled_without_source_window(self, app):
        from ui_result import ResultWindow

        win = ResultWindow(app, "texto", None, prompt="p", selected_text="t")
        assert str(win._replace_btn["state"]) == "disabled"
        assert str(win._regen_btn["state"]) == "normal"
        win.window.destroy()

    def test_append_after_close_is_ignored(self, app):
        from ui_result import ResultWindow

        win = ResultWindow(app, "", 1, streaming=True)
        win.window.destroy()
        win.append_chunk("x")
        win.finish("x", "gemini")


class TestRunAiAction:
    def test_streaming_opens_window_and_records_history(self, app):
        import ui_result

        thinking = MagicMock()

        def fake_generate(prompt, text, on_retry=None, on_chunk=None, on_status=None):
            on_chunk("Ho")
            on_chunk("la")
            return "Hola", "gemini"

        with (
            patch("ui_result.generate_text", side_effect=fake_generate),
            patch("ui_result.ConfigManager.get", return_value=True),
            patch("ui_result.ResultWindow") as mock_window,
        ):
            ui_result.run_ai_action(app, "p", "t", 99, thinking, label="≡  Resumir")

        mock_window.assert_called_once()
        mock_window.return_value.append_chunk.assert_any_call("Ho")
        mock_window.return_value.finish.assert_called_once_with("Hola", "gemini")
        assert app.history.entries()[0].label == "≡  Resumir"

    def test_error_shows_tooltip(self, app):
        import ui_result

        with (
            patch("ui_result.generate_text", side_effect=RuntimeError("falló")),
            patch("ui_result.ConfigManager.get", return_value=False),
        ):
            ui_result.run_ai_action(app, "p", "t", None, MagicMock())

        assert "falló" in app.tooltip.show.call_args[0][0]
        assert len(app.history) == 0


class TestWindowsBuild:
    def test_config_window_builds(self, app, tmp_path, monkeypatch):
        from ui_config import ConfigWindow

        monkeypatch.setattr("ui_config.StartupManager.is_enabled", lambda: False)
        cw = ConfigWindow(app)
        cw.show()
        _pump(app.root)
        assert cw.window.winfo_exists()
        cw._close()

    def test_floating_menu_binds_shortcuts(self, app):
        from ui_menu import FloatingMenu

        menu = FloatingMenu(app)
        with patch("ui_menu.ctypes.windll.user32.GetForegroundWindow", return_value=1):
            menu.show("Un texto de prueba")
        _pump(app.root)
        bound = menu.window.bind()
        assert "<Control-Key-r>" in bound or "<Control-r>" in bound
        menu.hide()
