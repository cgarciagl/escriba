import json

import pytest

import actions
from actions import display_shortcut, load_actions, shortcut_to_tk, write_defaults
from constants import AI_ACTIONS


@pytest.fixture(autouse=True)
def windows_shortcuts(monkeypatch):
    # Las expectativas usan la convención de Windows; la de macOS se prueba aparte.
    monkeypatch.setattr("actions.IS_MAC", False)


@pytest.fixture
def actions_file(tmp_path, monkeypatch):
    path = tmp_path / "actions.json"
    monkeypatch.setattr("actions.ACTIONS_FILE", str(path))
    return path


class TestShortcutToTk:
    @pytest.mark.parametrize("shortcut,expected", [
        ("Ctrl+R", "<Control-r>"),
        ("ctrl+1", "<Control-1>"),
        ("Ctrl+Shift+T", "<Control-Shift-t>"),
        ("Alt+F2", "<Alt-F2>"),
    ])
    def test_valid(self, shortcut, expected):
        assert shortcut_to_tk(shortcut, mac=False) == expected

    @pytest.mark.parametrize("shortcut", ["", "R", "Ctrl+", "Meta+R", "Ctrl+Ctrl+R", "Ctrl+Enter", None])
    def test_invalid(self, shortcut):
        assert shortcut_to_tk(shortcut, mac=False) is None
        assert shortcut_to_tk(shortcut, mac=True) is None

    @pytest.mark.parametrize("shortcut,expected", [
        ("Ctrl+R", "<Command-r>"),
        ("Cmd+R", "<Command-r>"),
        ("Alt+Shift+1", "<Option-Shift-1>"),
    ])
    def test_mac_maps_ctrl_to_command(self, shortcut, expected):
        assert shortcut_to_tk(shortcut, mac=True) == expected

    def test_cmd_maps_to_control_on_windows(self):
        assert shortcut_to_tk("Cmd+R", mac=False) == "<Control-r>"


class TestDisplayShortcut:
    def test_windows_unchanged(self):
        assert display_shortcut("Ctrl+R", mac=False) == "Ctrl+R"

    def test_mac_symbols(self):
        assert display_shortcut("Ctrl+R", mac=True) == "⌘R"
        assert display_shortcut("Ctrl+Shift+T", mac=True) == "⌘⇧T"

    def test_invalid_left_as_is(self):
        assert display_shortcut("raro", mac=True) == "raro"


class TestLoadActions:
    def test_defaults_when_no_file(self, actions_file):
        result, warnings = load_actions()
        assert len(result) == len(AI_ACTIONS)
        assert warnings == []
        assert all(a["shortcut_key"] for a in result)
        assert not actions_file.exists()  # no se crea solo

    def test_reads_user_file_and_fills_defaults(self, actions_file):
        actions_file.write_text(json.dumps([
            {"label": "★  Mi acción", "prompt": "Haz algo", "shortcut": "Ctrl+J"},
        ]), encoding="utf-8")

        result, warnings = load_actions()

        assert warnings == []
        assert result == [{
            "label": "★  Mi acción", "prompt": "Haz algo",
            "section": actions.DEFAULT_SECTION, "bootstyle": actions.DEFAULT_BOOTSTYLE,
            "shortcut": "Ctrl+J", "shortcut_key": "<Control-j>",
        }]

    def test_invalid_items_and_shortcuts_produce_warnings(self, actions_file):
        actions_file.write_text(json.dumps([
            {"label": "A", "prompt": "p", "shortcut": "Ctrl+J"},
            {"label": "B", "prompt": "p", "shortcut": "Ctrl+J"},
            {"label": "C", "prompt": "p", "shortcut": "nada"},
            {"label": "", "prompt": "p"},
            "texto",
        ]), encoding="utf-8")

        result, warnings = load_actions()

        assert [a["label"] for a in result] == ["A", "B", "C"]
        assert result[1]["shortcut_key"] is None
        assert result[2]["shortcut_key"] is None
        assert len(warnings) == 4

    def test_broken_json_falls_back_to_defaults(self, actions_file):
        actions_file.write_text("{ no es json", encoding="utf-8")
        result, warnings = load_actions()
        assert len(result) == len(AI_ACTIONS)
        assert len(warnings) == 1

    def test_empty_list_falls_back_to_defaults(self, actions_file):
        actions_file.write_text("[]", encoding="utf-8")
        result, warnings = load_actions()
        assert len(result) == len(AI_ACTIONS)
        assert warnings


class TestWriteDefaults:
    def test_creates_file_roundtrip(self, actions_file):
        path = write_defaults()
        assert path == str(actions_file)
        data = json.loads(actions_file.read_text(encoding="utf-8"))
        assert len(data) == len(AI_ACTIONS)
        assert "shortcut_key" not in data[0]
        result, warnings = load_actions()
        assert warnings == [] and len(result) == len(AI_ACTIONS)

    def test_does_not_overwrite_unless_asked(self, actions_file):
        actions_file.write_text('[{"label": "X", "prompt": "Y"}]', encoding="utf-8")
        write_defaults()
        assert len(json.loads(actions_file.read_text(encoding="utf-8"))) == 1
        write_defaults(overwrite=True)
        assert len(json.loads(actions_file.read_text(encoding="utf-8"))) == len(AI_ACTIONS)


from actions import action_icon, action_name, filter_actions, normalize_text


class TestPaletteSearch:
    ACTIONS = [
        {"label": "✎  Reescribir", "section": "Texto y Contenido"},
        {"label": "≡  Resumir", "section": "Texto y Contenido"},
        {"label": "◐  Traducir al español", "section": "Idiomas"},
        {"label": "◑  Traducir al inglés", "section": "Idiomas"},
        {"label": "⊙  Explicar código", "section": "Para desarrolladores"},
        {"label": "Sin icono", "section": "Otros"},
    ]

    def names(self, query):
        return [action_name(a) for a in filter_actions(self.ACTIONS, query)]

    def test_empty_query_returns_all(self):
        assert len(filter_actions(self.ACTIONS, "  ")) == len(self.ACTIONS)

    def test_accent_and_case_insensitive(self):
        assert self.names("ESPANOL") == ["Traducir al español"]
        assert self.names("código") == ["Explicar código"]

    def test_all_words_must_match(self):
        assert self.names("trad ingl") == ["Traducir al inglés"]

    def test_matches_section(self):
        assert self.names("idiomas") == ["Traducir al español", "Traducir al inglés"]

    def test_prefix_matches_first(self):
        # "re" está al inicio de Reescribir y Resumir; dentro de "desarrolladores" en Explicar código
        assert self.names("re")[:2] == ["Reescribir", "Resumir"]
        assert "Explicar código" in self.names("re")

    def test_no_match(self):
        assert self.names("zzz") == []

    def test_name_and_icon(self):
        assert action_name(self.ACTIONS[0]) == "Reescribir"
        assert action_icon(self.ACTIONS[0]) == "✎"
        assert action_name(self.ACTIONS[-1]) == "Sin icono"
        assert action_icon(self.ACTIONS[-1]) == "•"

    def test_normalize(self):
        assert normalize_text("  Ñandú ÁÉÍ ") == "nandu aei"
