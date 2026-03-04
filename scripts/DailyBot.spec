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
    ['../push_scheduler.py'],
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
# --- Post Build Script ---
import shutil
import os

# SPECPATH 是 .spec 文件所在的路径 (scripts/)
# root_path 应该是项目根目录 (scripts/.. -> DailyBot/)
# DISTPATH 是 PyInstaller 输出的目录 (通常是 dist/)
root_path = os.path.abspath(os.path.join(SPECPATH, '..'))
dist_target_path = DISTPATH

# 定义需要自动生成的外部配置文件 (源路径 -> 目标路径)
files_to_copy = [
    (os.path.join(root_path, 'config', 'config.yaml'), os.path.join(dist_target_path, 'config.yaml')),
    (os.path.join(root_path, '.env'), os.path.join(dist_target_path, '.env')),
]

print(f"\n[Post-Build] 正在检查配置文件生成 (Root: {root_path}, Dist: {dist_target_path})...")

for src, dst in files_to_copy:
    if os.path.exists(src):
        try:
            # 如果目标已存在，不覆盖以保留用户配置
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                print(f"  [Post-Build] 已成功生成默认配置文件: {os.path.basename(dst)}")
            else:
                print(f"  [Post-Build] 配置文件已存在，跳过生成: {os.path.basename(dst)}")
        except Exception as e:
            print(f"  [Post-Build] 拷贝配置文件失败 ({os.path.basename(dst)}): {e}")
    else:
        print(f"  [Post-Build] 未找到源文件，跳过: {os.path.basename(src)}")
