# -*- mode: python ; coding: utf-8 -*-
import os
src_dir = os.path.join(os.path.abspath('.'), 'src')
asset_exe = os.path.join(os.path.abspath('.'), 'assets', 'cli-proxy-api.exe')
binaries = [(asset_exe, '.')] if os.path.exists(asset_exe) else []
datas = []
for name in ('app_icon.ico', 'app_logo_dark.png', 'app_logo_light.png', 'logo.png'):
    path = os.path.join(os.path.abspath('.'), 'assets', name)
    if os.path.exists(path):
        datas.append((path, 'assets'))
a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[src_dir],
    binaries=binaries, datas=datas, hiddenimports=['yaml', 'PySide6.QtSvg'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='ModelDock', debug=False, strip=False,
    upx=True, console=False, argv_emulation=False,
    icon=os.path.join(os.path.abspath('.'), 'assets', 'app_icon.ico') if os.path.exists(os.path.join(os.path.abspath('.'), 'assets', 'app_icon.ico')) else None,
)
