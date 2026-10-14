"""Build a local macOS app with the installed Swift compiler and Python 3.10+."""
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin' or sys.version_info < (3, 10):
    raise SystemExit('Requires macOS and Python 3.10+')
app = root/'dist/HueForge Bambu Bridge.app/Contents'
(app/'MacOS').mkdir(parents=True, exist_ok=True)
(app/'Resources').mkdir(exist_ok=True)
subprocess.run(['swiftc', '-target', platform.machine() + '-apple-macosx12.0', '-O', str(root/'macos/main.swift'), '-o', str(app/'MacOS/Bridge'),
                '-framework', 'AppKit'], check=True)
shutil.copyfile(root/'macos/AppIcon.icns', app/'Resources/AppIcon.icns')
for name in ['hueforge_bambu.py', 'watch_hueforge.py']:
    shutil.copyfile(root/name, app/'Resources'/name)
with (app/'Info.plist').open('wb') as output:
    plistlib.dump(dict(CFBundleName='HueForge Bambu Bridge',
                      CFBundleDisplayName='HueForge Bambu Bridge',
                      CFBundleIdentifier='org.hueforge-bambu-bridge.desktop',
                      CFBundleExecutable='Bridge', CFBundlePackageType='APPL',
                      CFBundleIconFile='AppIcon',
                      CFBundleShortVersionString='0.3.0', CFBundleVersion='3',
                      LSMinimumSystemVersion='12.0', NSHighResolutionCapable=True,
                      CFBundleDevelopmentRegion='en', CFBundleLocalizations=['en'],
                      BridgePython=sys.executable), output)
print(app.parent)
