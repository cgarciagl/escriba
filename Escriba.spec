# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['escriba.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    icon=['escriba.ico'],
)
