"""Abre Google Chrome con la sesion de Vercel y deja la ventana abierta."""
import json
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

COOKIES = Path(r"c:\Users\daniela.alvarez\Downloads\vercel.com_cookies.json")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
url = sys.argv[1] if len(sys.argv) > 1 else "https://vercel.com/marketplace/neon"


def sanitizar(raw):
    if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
        return None
    cookie = {
        "name": str(raw["name"]),
        "value": str(raw["value"]),
        "domain": str(raw.get("domain") or "vercel.com"),
        "path": str(raw.get("path") or "/"),
        "secure": bool(raw.get("secure", True)),
        "httpOnly": bool(raw.get("httpOnly", False)),
    }
    exp = raw.get("expiry", raw.get("expirationDate"))
    if isinstance(exp, (int, float)) and exp > 0:
        cookie["expiry"] = int(exp)
    ss = str(raw.get("sameSite") or "").lower()
    cookie["sameSite"] = {"strict": "Strict", "lax": "Lax", "none": "None", "no_restriction": "None"}.get(ss, "Lax")
    return cookie


def main():
    raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
    options = Options()
    options.binary_location = str(CHROME)
    options.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='vercel_chrome_')}")
    options.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(service=Service(), options=options)
    driver.get("https://vercel.com")
    time.sleep(2)
    for raw_c in cookies:
        cookie = sanitizar(raw_c)
        if not cookie:
            continue
        try:
            driver.add_cookie(cookie)
        except Exception:
            cookie.pop("sameSite", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
    driver.get(url)
    time.sleep(4)
    print("browser", driver.capabilities.get("browserName"))
    print("url", driver.current_url.split("?")[0])
    print("title", driver.title)
    time.sleep(900)


if __name__ == "__main__":
    main()
