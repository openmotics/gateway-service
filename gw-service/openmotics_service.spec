# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['../src/openmotics_service.py'],
             pathex=['/app/gw-service'],
             binaries=[],
             datas=[('../src/gateway/migrations', 'gateway/migrations'), ('../src/gateway/webservice.py', 'gateway/'), ('../src/plugin_runtime', 'plugin_runtime'), ('../src/plugins', 'plugins'), ('../src/terms', 'terms')],
             hiddenimports=['cheroot.ssl', 'cheroot.ssl.builtin'],
             hookspath=['../hooks'],
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
          [],
          exclude_binaries=True,
          name='openmotics_service',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='openmotics_service')
