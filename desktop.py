"""
AI Arena — Desktop Launcher
Run this file to open AI Arena as a native desktop application.
Works on Windows and Linux.

Usage:
    python desktop.py          (dev mode)
    dist/AIArena/AIArena.exe   (installed app)
"""
import threading
import time
import sys
import os

def get_base_path():
    """Get path to bundled resources (PyInstaller) or project root (dev)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def start_server(base_path):
    """Start the FastAPI server in a background thread."""
    # When frozen, we need to chdir so main.py can find its files
    os.chdir(base_path)
    
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")

def main():
    base_path = get_base_path()
    
    # Start the web server in a background daemon thread
    server_thread = threading.Thread(target=start_server, args=(base_path,), daemon=True)
    server_thread.start()

    # Give the server a moment to boot
    time.sleep(2)

    try:
        import webview
    except ImportError:
        print("=" * 60)
        print("  pywebview is not installed!")
        print("  Install it with: pip install pywebview")
        print("=" * 60)
        sys.exit(1)

    # Create a native OS window pointing to the local server
    window = webview.create_window(
        title="AI Arena",
        url="http://127.0.0.1:8000",
        width=1200,
        height=800,
        resizable=True,
        min_size=(900, 600),
    )

    # Start the GUI event loop (blocks until window is closed)
    webview.start()

if __name__ == "__main__":
    main()
