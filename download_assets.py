import os
import shutil
import requests

def download_file(url, dest):
    print(f"  ↓ {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"    → {dest}")


def download_vendor():
    print("\n[2] Downloading vendor libraries")
    vendor = {
        "static/vendor/chessboard.min.css": "https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.css",
        "static/vendor/chessboard.min.js":  "https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.js",
        "static/vendor/chess.min.js":       "https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js",
        "static/vendor/jquery.min.js":      "https://code.jquery.com/jquery-3.7.1.min.js",
    }
    for dest, url in vendor.items():
        download_file(url, dest)

def main():
    print("=== AI Arena — asset setup ===")
    os.makedirs("static",        exist_ok=True)
    os.makedirs("static/vendor", exist_ok=True)


    download_vendor()
    print("\n✓ Done. Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

if __name__ == "__main__":
    main()
