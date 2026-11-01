"""Genera capturas de las ventanas reales (solo para revisión en CI)."""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import ImageGrab
import ttkbootstrap as tb

from plataforma import enable_dpi_awareness

enable_dpi_awareness()
root = tb.Window(themename="vapor")
root.geometry("1x1+0+0")

from history import History
from ui_common import ThinkingWindow, TooltipNotification
from ui_config import ConfigWindow
from ui_menu import FloatingMenu
from ui_result import ResultWindow

os.makedirs("shots", exist_ok=True)
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
    ImageGrab.grab(bbox=(x - 2, y - 2, x + w + 2, y + h + 2), all_screens=True).save(f"shots/{name}.png")


TEXT = ("Estimados colegas, les escribo para comentarles que la reunión del jueves "
        "se mueve al viernes a las 10, por favor confirmen su asistencia.")

with patch("ui_menu.get_foreground_window", return_value=1), \
     patch("ui_menu.bring_app_to_front"), patch("ui_menu.is_ready", return_value=True), \
     patch.object(root, "winfo_pointerx", return_value=300), \
     patch.object(root, "winfo_pointery", return_value=200):
    menu = FloatingMenu(app)
    menu.show(TEXT)
    menu.window.geometry("+300+200")
    shot(menu.window, "1_menu")
    menu.input.insert("1.0", "trad")
    menu._on_query_change()
    menu._move(1)
    shot(menu.window, "2_menu_filtrado")
    menu.input.delete("1.0", "end")
    menu.input.insert("1.0", "hazlo más breve y en tono amable")
    menu._on_query_change()
    shot(menu.window, "3_menu_instruccion")
    menu.hide()

t = ThinkingWindow(root, "≡  Resumir…", on_cancel=lambda: None)
pump()
shot(t.window, "4_pensando")
t.close()

r = ResultWindow(app, "", 1, prompt="p", selected_text=TEXT, label="✉  Mejorar Correo",
                 streaming=True, on_stop=lambda: None)
r.append_chunk("Estimados colegas:\n\nLes informo que la reunión prevista para el jueves")
shot(r.window, "5_resultado_streaming")
r.finish("Estimados colegas:\n\nLes informo que la reunión prevista para el jueves se ha "
         "trasladado al viernes a las 10:00 h. Les agradeceré que confirmen su asistencia.\n\n"
         "Saludos cordiales.", "gemini")
shot(r.window, "6_resultado")
r._toggle_view()
shot(r.window, "7_resultado_original")
r.window.destroy()

app.tooltip.show("Gemini HTTP 400: API key not valid. Please pass a valid API key.", "danger",
                 action=("Abrir configuración", lambda: None))
shot(app.tooltip.window, "8_error")
app.tooltip.hide()

with patch("ui_config.StartupManager.is_enabled", return_value=False):
    cw = ConfigWindow(app)
    cw.show(welcome=True)
    shot(cw.window, "9_config_bienvenida")
print("ok")
