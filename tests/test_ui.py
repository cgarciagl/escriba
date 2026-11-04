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
    from ui_common import configure_styles

    configure_styles(root)
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
        from actions import display_shortcut
        from ui_menu import button_text

        # "Ctrl+J" en Windows, "⌘J" en macOS
        expected = display_shortcut("Ctrl+J")
        assert button_text({"label": "X", "shortcut": "Ctrl+J", "shortcut_key": "<Control-j>"}).endswith(expected)
        assert button_text({"label": "X", "shortcut": "malo", "shortcut_key": None}) == "X"


class TestBuildItems:
    def test_custom_row_only_with_query(self):
        from ui_menu import build_items

        actions = [{"label": "✎  Reescribir", "section": "T"}]
        assert [i["kind"] for i in build_items(actions, "")] == ["action"]
        assert [i["kind"] for i in build_items(actions, "rees")] == ["action", "custom"]
        items = build_items(actions, "hazlo poético")
        assert [i["kind"] for i in items] == ["custom"]
        assert items[0]["prompt"] == "hazlo poético"


def _make_result(app, **kwargs):
    from ui_result import ResultWindow

    result = kwargs.pop("result", "")
    prev = kwargs.pop("prev", 1234)
    options = dict(prompt="p", selected_text="original del usuario")
    options.update(kwargs)
    return ResultWindow(app, result, prev, **options)


class TestResultWindow:
    def test_streaming_lifecycle(self, app):
        stop = MagicMock()
        win = _make_result(app, streaming=True, on_stop=stop)
        assert str(win._copy_btn["state"]) == "disabled"
        assert win._stop_btn.winfo_manager() == "pack"

        win.append_chunk("Hola ")
        win.append_chunk("mundo")
        assert win.text_widget.get("1.0", "end").strip() == "Hola mundo"

        win.finish("Hola mundo.", "gemini")
        assert win.text_widget.get("1.0", "end").strip() == "Hola mundo."
        assert str(win._copy_btn["state"]) == "normal"
        assert str(win._replace_btn["state"]) == "normal"
        assert win._stop_btn.winfo_manager() == ""
        win.window.destroy()

    def test_stop_calls_callback_and_marks_stopped(self, app):
        stop = MagicMock()
        win = _make_result(app, streaming=True, on_stop=stop)
        win.append_chunk("parcial")
        win._stop()
        stop.assert_called_once()
        win.mark_stopped()
        assert "Detenido" in win._badge["text"]
        assert str(win._copy_btn["state"]) == "normal"
        assert win.text_widget.get("1.0", "end").strip() == "parcial"
        win.window.destroy()

    def test_toggle_original_view(self, app):
        win = _make_result(app, result="resultado")
        _pump(app.root)
        assert win.text_widget.winfo_manager() == "pack"
        win._toggle_view()
        assert win.original_widget.winfo_manager() == "pack"
        assert win.text_widget.winfo_manager() == ""
        assert win.original_widget.get("1.0", "end").strip() == "original del usuario"
        win._toggle_view()
        assert win.text_widget.winfo_manager() == "pack"
        win.window.destroy()

    def test_replace_hidden_without_source_window(self, app):
        win = _make_result(app, result="texto", prev=None)
        assert win._replace_btn.winfo_manager() == ""
        assert str(win._regen_btn["state"]) == "normal"
        win.window.destroy()

    def test_shortcuts_bound(self, app):

        win = _make_result(app, result="texto")
        bound = " ".join(win.window.bind())
        assert "Return" in bound and "Key-o" in bound and "Escape" in bound
        win.window.destroy()

    def test_append_after_close_is_ignored(self, app):
        win = _make_result(app, streaming=True)
        win.window.destroy()
        win.append_chunk("x")
        win.finish("x", "gemini")


class TestRunAiAction:
    def _session(self, app, prompt="p", text="t", prev=99, label="≡  Resumir"):
        from ui_result import _ResultSession

        session = _ResultSession(app, prompt, text, prev, label)
        session.thinking = MagicMock()
        return session

    def test_streaming_opens_window_and_records_history(self, app):
        import ui_result

        session = self._session(app)

        def fake_generate(prompt, text, on_retry=None, on_chunk=None, on_status=None, cancel_event=None):
            assert cancel_event is session.cancel_event
            on_chunk("Ho")
            on_chunk("la")
            return "Hola", "gemini"

        with (
            patch("ui_result.generate_text", side_effect=fake_generate),
            patch("ui_result.ConfigManager.get", return_value=True),
            patch("ui_result.ResultWindow") as mock_window,
        ):
            ui_result.run_ai_action(app, session)

        mock_window.assert_called_once()
        mock_window.return_value.append_chunk.assert_any_call("Ho")
        mock_window.return_value.finish.assert_called_once_with("Hola", "gemini")
        assert app.history.entries()[0].label == "≡  Resumir"

    def test_config_error_offers_settings(self, app):
        import ui_result

        with (
            patch("ui_result.generate_text", side_effect=ValueError("API Key de Google Gemini no configurada.")),
            patch("ui_result.ConfigManager.get", return_value=False),
        ):
            ui_result.run_ai_action(app, self._session(app))

        args, kwargs = app.tooltip.show.call_args
        assert "API Key" in args[0] and args[1] == "danger"
        assert kwargs["action"][0] == "Abrir configuración"
        assert len(app.history) == 0

    def test_transient_error_offers_retry(self, app):
        import ui_result

        with (
            patch("ui_result.generate_text", side_effect=RuntimeError("Error de red: sin conexión")),
            patch("ui_result.ConfigManager.get", return_value=False),
        ):
            ui_result.run_ai_action(app, self._session(app))
        assert app.tooltip.show.call_args.kwargs["action"][0] == "Reintentar"

    def test_cancel_is_quiet(self, app):
        import ui_result
        from ai_clients import CancelledByUser

        with (
            patch("ui_result.generate_text", side_effect=CancelledByUser()),
            patch("ui_result.ConfigManager.get", return_value=False),
        ):
            ui_result.run_ai_action(app, self._session(app))
        args, _ = app.tooltip.show.call_args
        assert args[1] == "info" and "cancelada" in args[0]


class TestTooltip:
    def test_error_stays_and_runs_action(self, app):
        from ui_common import TooltipNotification

        action = MagicMock()
        tip = TooltipNotification(app.root)
        tip.show("Algo falló", "danger", action=("Abrir configuración", action))
        _pump(app.root)
        assert tip.window.winfo_exists()
        buttons = [w for w in tip.window.winfo_children()[0].winfo_children()[0].winfo_children()
                   if w.winfo_class() == "TButton"]
        assert len(buttons) == 1
        buttons[0].invoke()
        action.assert_called_once()
        assert tip.window is None


class TestWindowsBuild:
    def test_config_window_builds_with_welcome(self, app, monkeypatch):
        from ui_config import ConfigWindow

        monkeypatch.setattr("ui_config.StartupManager.is_enabled", lambda: False)
        cw = ConfigWindow(app)
        cw.show(welcome=True)
        _pump(app.root)
        assert cw.window.winfo_exists()
        assert "bienvenida" in cw.status_var.get()
        cw._close()

    @pytest.fixture
    def menu(self, app):
        from ui_menu import FloatingMenu

        menu = FloatingMenu(app)
        with patch("ui_menu.get_foreground_window", return_value=1), \
             patch("ui_menu.bring_app_to_front"), \
             patch("ui_menu.is_ready", return_value=True):
            menu.show("Un texto de prueba")
        _pump(app.root)
        yield menu
        menu.hide()

    def test_menu_binds_action_shortcuts(self, menu):
        bound = menu.window.bind()
        assert any(b.endswith("Key-r>") for b in bound), bound

    def _type(self, menu, text):
        menu.input.delete("1.0", "end")
        menu.input.insert("1.0", text)
        menu._on_query_change()

    def test_typing_filters_and_offers_custom_prompt(self, menu):
        self._type(menu, "espanol")
        kinds = [(i["kind"], i.get("action", {}).get("label", "")) for i in menu._items]
        assert kinds[0][1].endswith("Traducir al español")
        assert kinds[-1][0] == "custom"
        assert len(menu._rows) == 2

    def test_arrows_and_enter_run_selected(self, menu):
        self._type(menu, "hazlo más formal")
        assert [i["kind"] for i in menu._items] == ["custom"]
        with patch("ui_menu.start_ai_action") as start:
            menu._run_selected()
        args = start.call_args[0]
        assert args[1] == "hazlo más formal" and args[2] == "Un texto de prueba"

    def test_move_wraps_around(self, menu):
        n = len(menu._rows)
        menu._move(-1)
        assert menu._sel == n - 1
        menu._move(1)
        assert menu._sel == 0

    def test_not_ready_shows_settings_hint(self, app):
        from ui_menu import FloatingMenu

        menu = FloatingMenu(app)
        with patch("ui_menu.is_ready", return_value=False):
            menu.show("texto")
        assert menu.window is None
        assert app.tooltip.show.call_args.kwargs["action"][0] == "Abrir configuración"

    def test_placeholder_centered_and_hides_on_input(self, menu):
        place_info = menu._placeholder.place_info()
        assert float(place_info["rely"]) == 0.5
        assert place_info["anchor"] == "w"
        self._type(menu, "algo")
        assert not menu._placeholder.winfo_ismapped()
        self._type(menu, "")
        assert menu._placeholder.winfo_ismapped()


class TestTrayMenu:
    def test_history_items_with_and_without_entries(self, app):
        from tray import TrayIconManager

        tray = TrayIconManager(app)
        # Sin historial
        items_empty = list(tray._history_items())
        assert len(items_empty) == 1
        assert "(sin respuestas todavía)" in items_empty[0].text

        # Con historial
        entry = app.history.add("Resumir", "p", "t", "Resultado de prueba", "gemini")
        items = list(tray._history_items())
        # Debe tener el item del historial, el separador y borrar historial
        assert len(items) == 3
        history_item = items[0]
        assert "Resumir" in history_item.text
        # Invocar la acción debe programar open_history_entry con la entrada correcta
        history_item(None)
        app.schedule.assert_called_with(app.open_history_entry, entry)
