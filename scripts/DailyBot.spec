# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 需要包含的静态资源文件夹和配置文件
added_files = [
    ('../config/config.yaml', 'config'),
    ('../.env', '.'),
    ('../prompts', 'prompts'),
    ('../api', 'api'),
    ('../crawlers', 'crawlers'),
    ('../oauth', 'oauth'),
    ('../providers', 'providers'),
    ('../request', 'request'),
    ('../rpa', 'rpa'),
    ('../token_storage', 'token_storage'),
    ('../workflows', 'workflows'),
    ('../utils', 'utils'),
    ('../common', 'common'),
    ('../enums', 'enums'),
    ('../exceptions', 'exceptions'),
    ('D:/python/Lib/site-packages/playwright/driver', 'driver'),
    ('D:/python/Lib/site-packages/playwright_stealth/js', 'playwright_stealth/js'),
]

# 隐藏导入列表 (PyInstaller 无法自动识别的动态导入)
hidden_imports = [
    'crawlers.impl',
    'rpa.impl',
    'workflows.impl',
    'providers.impl',
    'oauth.impl',
    'request.platforms.impl',
    'lark_oapi',
    'playwright',
    'playwright_stealth',
    'playwright._impl._driver',
    'playwright._impl._browser_type',
]

a = Analysis(
    ['../main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DailyBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../assest/favicon.ico'] if os.path.exists('../assest/favicon.ico') else None,
)
