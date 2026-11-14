# -*- mode: python ; coding: utf-8 -*-
#
# Windows: dist\Escriba.exe (un solo archivo, sin consola)
# macOS:   dist/Escriba.app (bundle de barra de menús, sin ícono en el Dock)
# Linux:   dist/Escriba (ejecutable autónomo X11)
#
import os
import sys

sys.path.insert(0, os.path.abspath(SPECPATH))  # para importar constants
IS_MAC = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')

COMMON_IMPORTS = ['constants', 'config', 'actions', 'history', 'plataforma', 'ai_clients',
                  'updater', 'ui_windows', 'ui_common', 'ui_config', 'ui_menu', 'ui_result', 'tray']
if IS_MAC:
    PLATFORM_IMPORTS = ['macos', 'pynput.keyboard._darwin', 'pynput.mouse._darwin',
                        'AppKit', 'Quartz', 'pystray._darwin']
elif IS_LINUX:
    PLATFORM_IMPORTS = ['linux_platform', 'pynput.keyboard._xorg', 'pynput.mouse._xorg',
                        'pystray._xorg', 'pystray._appindicator',
                        'PIL._tkinter_finder', 'PIL._imagingtk']
else:
    PLATFORM_IMPORTS = ['hotkey', 'startup']


a = Analysis(
    ['escriba.py'],
    pathex=[],
    binaries=[],
    datas=[('escriba.ico', '.'), ('escriba_logo.png', '.')],
    hiddenimports=COMMON_IMPORTS + PLATFORM_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # científicos / datos
        'numpy', 'pandas', 'scipy', 'matplotlib', 'sklearn',
        'statsmodels', 'sympy', 'numba', 'numexpr', 'tables',
        # notebook / IPython
        'IPython', 'ipykernel', 'ipywidgets', 'notebook', 'jupyter',
        'nbformat', 'nbconvert', 'traitlets', 'tornado',
        # herramientas de desarrollo
        'pytest', 'unittest', 'doctest', 'pdb', 'cProfile',
        'sphinx', 'numpydoc',
        # multimedia / gráficos no utilizados
        'cv2', 'skimage', 'imageio', 'moviepy',
        # utilidades no requeridas
        'setuptools', 'pkg_resources',
        'pygments', 'colorama',
        'pydoc_fork', 'pydoc',
        'xmlrpc', 'ftplib', 'imaplib', 'smtplib', 'poplib',
        'sqlite3', 'bz2', 'lzma',
        # dependencias eliminadas del proyecto
        'pyautogui', 'mouseinfo', 'pyscreeze',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

if not IS_MAC:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='Escriba',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None if IS_LINUX else ['escriba.ico'],
    )
else:
    from constants import APP_VERSION

    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Escriba',
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,   # p. ej. "Developer ID Application: Tu Nombre (TEAMID)"
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Escriba')
    app = BUNDLE(
        coll,
        name='Escriba.app',
        icon='escriba.ico',   # PyInstaller lo convierte a .icns (requiere Pillow)
        bundle_identifier='com.cgarciagl.escriba',
        info_plist={
            'CFBundleName': 'Escriba',
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'LSUIElement': True,             # sin ícono en el Dock
            'LSMinimumSystemVersion': '11.0',
            'NSHighResolutionCapable': True,
        },
    )
