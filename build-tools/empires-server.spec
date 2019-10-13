# -*- mode: python -*-
import os
block_cipher = None


a = Analysis(['empires-server.py'],
             pathex=['C:\\empires'],
             binaries=[],
             datas=[],
             hiddenimports=['engineio.async_drivers.threading'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='empires-server',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True, icon='build-tools/icon.ico')
