"""Genera capturas PNG de las ventanas reales en shots/ para revisar la interfaz.

Lo ejecuta la CI de Windows (artefacto "capturas"); también puede correrse
localmente: python tools/capturas.py [--lang es|en]
"""
import argparse
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parser = argparse.ArgumentParser()
parser.add_argument("--lang", choices=("es", "en"), default="es")
parser.add_argument("--out", default="shots")
args, _ = parser.parse_known_args()

import config as cfg  # noqa: E402
_tmp_cfg_dir = tempfile.mkdtemp(prefix="escriba_shots_")
cfg.CONFIG_FILE = os.path.join(_tmp_cfg_dir, "config.json")
cfg.LEGACY_CONFIG_FILE = os.path.join(_tmp_cfg_dir, "legacy.json")
cfg.ConfigManager._cache = {"api_key": "", "model": "gemini-3.5-flash-lite", "autostart": False, "language": args.lang}

import actions as act  # noqa: E402
act.ACTIONS_FILE = os.path.join(_tmp_cfg_dir, "actions.json")

from PIL import ImageGrab  # noqa: E402
import ttkbootstrap as tb  # noqa: E402

from plataforma import enable_dpi_awareness  # noqa: E402

enable_dpi_awareness()
root = tb.Window(themename="vapor")
root.geometry("1x1+0+0")
from ui_common import configure_styles  # noqa: E402
configure_styles(root)

from history import History  # noqa: E402
from ui_common import ThinkingWindow, TooltipNotification  # noqa: E402
from ui_config import ConfigWindow  # noqa: E402
from ui_menu import FloatingMenu  # noqa: E402
from ui_result import ResultWindow  # noqa: E402

OUT_DIR = args.out
os.makedirs(OUT_DIR, exist_ok=True)
app = MagicMock()
app.root = root
app.history = History()
app.schedule.side_effect = lambda cb, *a: cb(*a)
app.tooltip = TooltipNotification(root)


def pump():
    for _ in range(30):
        root.update()


def shot(win, name):
    pump()
    win.lift()
    win.attributes("-topmost", True)
    win.attributes("-alpha", 1.0)
    pump()
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    ImageGrab.grab(bbox=(x - 2, y - 2, x + w + 2, y + h + 2), all_screens=True).save(
        os.path.join(OUT_DIR, f"{name}.png")
    )


if args.lang == "en":
    TEXT = ("Dear colleagues, I am writing to let you know that Thursday's meeting "
            "has been moved to Friday at 10 AM. Please confirm your attendance.")
    FILTER_Q = "trans"
    CUSTOM_Q = "make it shorter and friendlier"
    THINK_LBL = "≡  Summarize…"
    RES_LBL = "✉  Improve Email"
    CHUNK_PART = "Dear colleagues,\n\nI would like to inform you that Thursday's meeting"
    RES_FINAL = ("Dear colleagues,\n\nPlease note that Thursday's meeting has been moved "
                 "to Friday at 10:00 AM. Kindly confirm your attendance.\n\nBest regards.")
    ERR_ACTION = "Open settings"
else:
    TEXT = ("Estimados colegas, les escribo para comentarles que la reunión del jueves "
            "se mueve al viernes a las 10, por favor confirmen su asistencia.")
    FILTER_Q = "trad"
    CUSTOM_Q = "hazlo más breve y en tono amable"
    THINK_LBL = "≡  Resumir…"
    RES_LBL = "✉  Mejorar Correo"
    CHUNK_PART = "Estimados colegas:\n\nLes informo que la reunión prevista para el jueves"
    RES_FINAL = ("Estimados colegas:\n\nLes informo que la reunión prevista para el jueves se ha "
                 "trasladado al viernes a las 10:00 h. Les agradeceré que confirmen su asistencia.\n\n"
                 "Saludos cordiales.")
    ERR_ACTION = "Abrir configuración"

with patch("ui_menu.get_foreground_window", return_value=1), \
     patch("ui_menu.bring_app_to_front"), patch("ui_menu.is_ready", return_value=True), \
     patch.object(root, "winfo_pointerx", return_value=300), \
     patch.object(root, "winfo_pointery", return_value=200):
    menu = FloatingMenu(app)
    menu.show(TEXT)
    menu.window.geometry("+300+40")
    shot(menu.window, "1_menu")
    menu.input.insert("1.0", FILTER_Q)
    menu._on_query_change()
    menu._move(1)
    shot(menu.window, "2_menu_filtrado")
    menu.input.delete("1.0", "end")
    menu.input.insert("1.0", CUSTOM_Q)
    menu._on_query_change()
    shot(menu.window, "3_menu_instruccion")
    menu.hide()
    menu.show("")
    menu.window.geometry("+300+40")
    shot(menu.window, "3b_menu_redaccion")
    menu.hide()

t = ThinkingWindow(root, THINK_LBL, on_cancel=lambda: None)
pump()
t.window.geometry("+300+300")
shot(t.window, "4_pensando")
t.close()

r = ResultWindow(app, "", 1, prompt="p", selected_text=TEXT, label=RES_LBL,
                 streaming=True, on_stop=lambda: None)
r.append_chunk(CHUNK_PART)
shot(r.window, "5_resultado_streaming")
r.finish(RES_FINAL, "gemini")
shot(r.window, "6_resultado")
r._toggle_view()
shot(r.window, "7_resultado_original")
r.view_var.set("diff")
r._switch_view()
shot(r.window, "7b_resultado_cambios")
r.window.destroy()

app.tooltip.show("Gemini HTTP 400: API key not valid. Please pass a valid API key.", "danger",
                 action=(ERR_ACTION, lambda: None))
shot(app.tooltip.window, "8_error")
app.tooltip.hide()

with patch("ui_config.StartupManager.is_enabled", return_value=False):
    cw = ConfigWindow(app)
    cw.show(welcome=True)
    shot(cw.window, "9_config_bienvenida")
    cw.window.nametowidget(cw.window.winfo_children()[0]).update()
    nb = [w for w in cw.window.winfo_children()[0].winfo_children() if w.winfo_class() == "TNotebook"][0]
    nb.select(1)
    shot(cw.window, "10_config_alternativo")
    nb.select(2)
    shot(cw.window, "11_config_acciones")
    nb.select(3)
    shot(cw.window, "12_config_general")
print("ok")
