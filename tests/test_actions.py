import json

import pytest

import actions
from actions import load_actions, shortcut_to_tk, write_defaults
from constants import AI_ACTIONS


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
        assert shortcut_to_tk(shortcut) == expected

    @pytest.mark.parametrize("shortcut", ["", "R", "Ctrl+", "Meta+R", "Ctrl+Ctrl+R", "Ctrl+Enter", None])
    def test_invalid(self, shortcut):
        assert shortcut_to_tk(shortcut) is None


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
