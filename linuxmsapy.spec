# -*- mode: python -*-
a = Analysis(['msaRun.py'],
             pathex=['/home/eric/workspace/msapy'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='msapy',
          debug=False,
          strip=None,
          upx=True,
          console=True )
