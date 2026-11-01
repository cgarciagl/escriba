"""
Escriba — Fachada de la interfaz gráfica.

La UI está repartida en varios módulos; este archivo los reexporta para que
el resto de la app (y código existente) pueda seguir importando desde aquí:

- ui_common.py  → paleta _FM_*, helpers, TooltipNotification, ThinkingWindow, SplashBanner
- ui_config.py  → ConfigWindow
- ui_menu.py    → FloatingMenu (paleta de comandos con instrucción libre integrada)
- ui_result.py  → ResultWindow, run_ai_action, start_ai_action
"""

from ui_common import (  # noqa: F401
    SplashBanner,
    ThinkingWindow,
    TooltipNotification,
    apply_dark_style,
    center_window,
    fade_window,
    place_near_pointer,
    position_bottom_right,
)
from ui_config import ConfigWindow  # noqa: F401
from ui_menu import FloatingMenu  # noqa: F401
from ui_result import ResultWindow, run_ai_action, start_ai_action  # noqa: F401
