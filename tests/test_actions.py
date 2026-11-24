import json

import pytest

import actions
from actions import (
    action_icon,
    action_name,
    display_shortcut,
    expand_prompt_vars,
    export_actions,
    extract_prompt_inputs,
    filter_actions,
    import_actions,
    load_actions,
    normalize_text,
    shortcut_to_tk,
    strip_code_fences,
    write_defaults,
)
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


class TestSaveAndVars:
    def test_save_actions_persists_new_fields(self, tmp_path, monkeypatch):
        target = str(tmp_path / "actions.json")
        monkeypatch.setattr(actions, "ACTIONS_FILE", target)

        warnings = actions.save_actions([
            {
                "label": "✎  Test",
                "prompt": "Haz algo",
                "auto_replace": True,
                "strip_markdown": True,
                "mode": "both",
                "temperature": 0.35,
                "model": "gemini-2.5-pro",
            },
        ])
        assert warnings == []
        loaded, load_warnings = actions.load_actions()
        assert load_warnings == []
        assert loaded[0]["auto_replace"] is True
        assert loaded[0]["strip_markdown"] is True
        assert loaded[0]["mode"] == "both"
        assert loaded[0]["temperature"] == 0.35
        assert loaded[0]["model"] == "gemini-2.5-pro"

    def test_invalid_mode_and_temperature_emit_warnings(self, actions_file):
        actions_file.write_text(json.dumps([
            {"label": "X", "prompt": "Y", "mode": "invalido", "temperature": 9.5},
        ]), encoding="utf-8")
        loaded, warnings = load_actions()
        assert len(loaded) == 1
        assert "mode" not in loaded[0]
        assert "temperature" not in loaded[0]
        assert any("modo" in w for w in warnings)
        assert any("temperatura" in w for w in warnings)

    def test_export_and_import_roundtrip(self, tmp_path):
        export_path = tmp_path / "pack.json"
        sample = [
            {
                "label": "✉  Redactar correo",
                "prompt": "Redacta un correo para {input:Destinatario}",
                "section": "Redacción",
                "mode": "compose",
                "temperature": 0.4,
            }
        ]
        export_actions(str(export_path), sample)
        imported, warnings = import_actions(str(export_path))
        assert warnings == []
        assert imported[0]["mode"] == "compose"
        assert imported[0]["temperature"] == 0.4

    def test_strip_code_fences(self):
        fenced = "```sql\nSELECT * FROM t;\n```"
        assert strip_code_fences(fenced) == "SELECT * FROM t;"
        assert strip_code_fences("SELECT 1;") == "SELECT 1;"

    def test_extract_prompt_inputs_preserves_order_and_uniqueness(self):
        prompt = "Traduce a {input:Idioma} con tono {input:Tono} manteniendo {input:Idioma}"
        assert extract_prompt_inputs(prompt) == ["Idioma", "Tono"]

    def test_expand_prompt_vars_replaces_clipboard_date_and_inputs(self, monkeypatch):
        import pyperclip

        monkeypatch.setattr(pyperclip, "paste", lambda: "texto copiado")
        expanded = expand_prompt_vars(
            "Clip:{clipboard} Fecha:{date} Hora:{time} FH:{datetime} Extra:{input:Idioma} App:{app}",
            extra_vars={"Idioma": "francés", "app": "code"},
        )
        assert "Clip:texto copiado" in expanded
        assert "{date}" not in expanded
        assert "{time}" not in expanded
        assert "{datetime}" not in expanded
        assert "Extra:francés" in expanded
        assert expanded.endswith("App:code")


class TestAppsAndCustomSave:
    def test_apps_normalization_and_matching(self, actions_file):
        from actions import action_matches_app, save_actions

        warnings = save_actions([
            {"label": "💻  Código", "prompt": "Revisa en {app}", "apps": "Code, Cursor"},
            {"label": "🌐  Global", "prompt": "General"},
        ])
        assert warnings == []
        loaded, _ = load_actions()
        assert loaded[0]["apps"] == ["code", "cursor"]
        assert "apps" not in loaded[1]
        assert action_matches_app(loaded[0], "code") is True
        assert action_matches_app(loaded[0], "notepad") is False
        assert action_matches_app(loaded[0], "") is True
        assert action_matches_app(loaded[1], "notepad") is True

    def test_add_custom_action_appends_and_deduplicates_label(self, actions_file):
        from actions import add_custom_action

        add_custom_action("Mi resumen", "Resume en 2 líneas")
        add_custom_action("Mi resumen", "Resume en 3 líneas")
        loaded, _ = load_actions()
        labels = [a["label"] for a in loaded]
        assert "✨  Mi resumen" in labels
        assert "✨  Mi resumen (2)" in labels
        added = [a for a in loaded if a["label"] == "✨  Mi resumen"][0]
        assert added["section"] == "Personalizadas"
        assert added["mode"] == "both"


class TestBilingualActions:
    def test_default_actions_follow_configured_language(self, actions_file):
        from config import ConfigManager

        ConfigManager.set_language("en")
        en_actions, _ = load_actions()
        assert en_actions[0]["label"] == "✎  Rewrite"
        assert en_actions[0]["section"] == "Text & Content"

        ConfigManager.set_language("es")
        es_actions, _ = load_actions()
        assert es_actions[0]["label"] == "✎  Reescribir"
        assert es_actions[0]["section"] == "Texto y Contenido"

    def test_custom_actions_file_is_preserved_across_language_change(self, actions_file):
        from actions import save_actions
        from config import ConfigManager

        save_actions([{"label": "★  Custom", "prompt": "My prompt"}])
        ConfigManager.set_language("en")
        loaded, _ = load_actions()
        assert [a["label"] for a in loaded] == ["★  Custom"]

    def test_is_translation_action(self):
        from actions import is_translation_action

        assert is_translation_action({"label": "◐  Traducir al español", "prompt": "..."}) is True
        assert is_translation_action({"label": "Custom", "prompt": "Translate to French"}) is True
        assert is_translation_action({"label": "✎  Rewrite", "prompt": "Rewrite text"}) is False

    def test_expand_lang_uses_configured_language(self):
        from config import ConfigManager

        ConfigManager.set_language("en")
        assert expand_prompt_vars("Respond in {lang}") == "Respond in en"


