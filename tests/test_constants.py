from constants import (
    AI_ACTIONS,
    APP_NAME,
    APP_VERSION,
    CONFIG_FILE,
    GEMINI_BASE,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODELS,
    STARTUP_KEY,
)

_VALID_SECTIONS = {"Texto y Contenido", "Idiomas", "Para desarrolladores"}
_VALID_BOOTSTYLES = {
    "info-outline",
    "warning-outline",
    "danger-outline",
    "secondary-outline",
    "primary",
    "primary-outline",
}


class TestAppConstants:
    def test_app_name(self):
        assert APP_NAME == "Escriba"

    def test_app_version(self):
        assert isinstance(APP_VERSION, str)
        assert len(APP_VERSION) > 0

    def test_config_file_ends_with_json(self):
        assert CONFIG_FILE.endswith("config.json")

    def test_startup_key_is_valid_registry_path(self):
        assert STARTUP_KEY.startswith("Software\\")
        assert "Run" in STARTUP_KEY

    def test_gemini_constants(self):
        assert "googleapis.com" in GEMINI_BASE
        assert GEMINI_DEFAULT_MODEL == "gemini-3.5-flash-lite"
        assert "gemini-3.5-flash-lite" in GEMINI_FALLBACK_MODELS


class TestAIActions:
    def test_total_count(self):
        assert len(AI_ACTIONS) == 10

    def test_every_action_has_required_keys(self):
        for i, action in enumerate(AI_ACTIONS):
            assert "label" in action, f"Action {i} missing 'label'"
            assert "prompt" in action, f"Action {i} missing 'prompt'"
            assert "bootstyle" in action, f"Action {i} missing 'bootstyle'"
            assert "section" in action, f"Action {i} missing 'section'"

    def test_every_action_has_non_empty_prompt(self):
        for action in AI_ACTIONS:
            assert action["prompt"].strip(), (
                f"Action '{action['label']}' has empty prompt"
            )

    def test_every_action_has_non_empty_label(self):
        for action in AI_ACTIONS:
            assert action["label"].strip(), f"Action has empty label"

    def test_all_sections_are_known(self):
        for action in AI_ACTIONS:
            assert action["section"] in _VALID_SECTIONS, (
                f"Unknown section '{action['section']}' in '{action['label']}'"
            )

    def test_texto_y_contenido_section_count(self):
        text_actions = [a for a in AI_ACTIONS if a["section"] == "Texto y Contenido"]
        assert len(text_actions) == 5

    def test_idiomas_section_count(self):
        lang_actions = [a for a in AI_ACTIONS if a["section"] == "Idiomas"]
        assert len(lang_actions) == 2

    def test_desarrolladores_section_count(self):
        dev_actions = [a for a in AI_ACTIONS if a["section"] == "Para desarrolladores"]
        assert len(dev_actions) == 3

    def test_no_duplicate_labels(self):
        labels = [a["label"] for a in AI_ACTIONS]
        assert len(labels) == len(set(labels)), f"Duplicate labels: {labels}"

    def test_every_action_has_valid_shortcut(self):
        from actions import shortcut_to_tk

        for action in AI_ACTIONS:
            assert "shortcut" in action, f"Action '{action['label']}' missing 'shortcut'"
            assert shortcut_to_tk(action["shortcut"]), (
                f"Invalid shortcut '{action['shortcut']}' for '{action['label']}'"
            )

    def test_shortcuts_avoid_common_editing_keys(self):
        used = {a["shortcut"] for a in AI_ACTIONS}
        assert not used & {"Ctrl+X", "Ctrl+S", "Ctrl+F", "Ctrl+C", "Ctrl+V", "Ctrl+Z", "Ctrl+A"}

    def test_shortcuts_are_unique(self):
        shortcuts = [a["shortcut"] for a in AI_ACTIONS]
        assert len(shortcuts) == len(set(shortcuts))

    def test_bootstyle_is_valid(self):
        for action in AI_ACTIONS:
            assert action["bootstyle"] in _VALID_BOOTSTYLES, (
                f"Invalid bootstyle '{action['bootstyle']}' in '{action['label']}'"
            )

    def test_rewrite_action(self):
        rewrite = AI_ACTIONS[0]
        assert rewrite["label"] == "✎  Reescribir"
        assert "claridad" in rewrite["prompt"]
        assert rewrite["section"] == "Texto y Contenido"

    def test_fix_sql_action(self):
        fix_sql = [a for a in AI_ACTIONS if "Fix SQL" in a["label"]][0]
        assert fix_sql["section"] == "Para desarrolladores"
        assert "SQL" in fix_sql["prompt"]

    def test_translate_actions_have_correct_prompts(self):
        to_es = [a for a in AI_ACTIONS if "español" in a["label"]][0]
        to_en = [a for a in AI_ACTIONS if "inglés" in a["label"]][0]
        assert "traducir" in to_es["prompt"].lower()
        assert "translate" in to_en["prompt"].lower()
