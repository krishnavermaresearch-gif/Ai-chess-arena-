"""
AI Arena — Build Script
Packages the entire application into a standalone .exe (Windows) or binary (Linux).

Usage:
    python build.py
    
Output:
    dist/AIArena/AIArena.exe   (Windows)
    dist/AIArena/AIArena        (Linux)
"""
import PyInstaller.__main__
import os

# All project files that need to be bundled inside the .exe
data_files = [
    ('main.py', '.'),
    ('index.html', '.'),
    ('style.css', '.'),
    ('script.js', '.'),
    ('download_assets.py', '.'),
    ('requirements.txt', '.'),
    ('.env.example', '.'),
]

# Add static/vendor directory if it exists
if os.path.isdir('static/vendor'):
    data_files.append(('static/vendor', 'static/vendor'))

# Build the --add-data arguments
add_data_args = []
for src, dest in data_files:
    if os.path.exists(src):
        sep = ';' if os.name == 'nt' else ':'
        add_data_args.extend(['--add-data', f'{src}{sep}{dest}'])

PyInstaller.__main__.run([
    'desktop.py',                     # Entry point
    '--name', 'AIArena',              # Output name
    '--onedir',                       # Create folder with all files (faster startup than --onefile)
    '--windowed',                     # No console window (GUI app)
    '--noconfirm',                    # Overwrite previous build
    '--clean',                        # Clean cache
    *add_data_args,                   # Bundle project files
    '--hidden-import', 'uvicorn',
    '--hidden-import', 'uvicorn.logging',
    '--hidden-import', 'uvicorn.loops',
    '--hidden-import', 'uvicorn.loops.auto',
    '--hidden-import', 'uvicorn.protocols',
    '--hidden-import', 'uvicorn.protocols.http',
    '--hidden-import', 'uvicorn.protocols.http.auto',
    '--hidden-import', 'uvicorn.protocols.websockets',
    '--hidden-import', 'uvicorn.protocols.websockets.auto',
    '--hidden-import', 'uvicorn.lifespan',
    '--hidden-import', 'uvicorn.lifespan.on',
    '--hidden-import', 'uvicorn.lifespan.off',
    '--hidden-import', 'fastapi',
    '--hidden-import', 'fastapi.middleware',
    '--hidden-import', 'fastapi.middleware.cors',
    '--hidden-import', 'chess',
    '--hidden-import', 'dotenv',
    '--hidden-import', 'webview',
    '--collect-all', 'chess',
    '--collect-all', 'webview',
])

print()
print("=" * 60)
print("  BUILD COMPLETE!")
print()
if os.name == 'nt':
    print("  Your app is at: dist/AIArena/AIArena.exe")
else:
    print("  Your app is at: dist/AIArena/AIArena")
print()
print("  Share the entire dist/AIArena/ folder.")
print("  Users just double-click AIArena.exe to play!")
print("=" * 60)
