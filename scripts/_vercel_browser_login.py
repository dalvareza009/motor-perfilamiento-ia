"""Abre Google Chrome (no Edge), carga cookies de Vercel y autoriza el login de dispositivo."""
import json
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

COOKIES = Path(r"c:\Users\daniela.alvarez\Downloads\vercel.com_cookies.json")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
url = sys.argv[1] if len(sys.argv) > 1 else "https://vercel.com/dashboard"


def sanitizar(raw):
    if not isinstance(raw, dict) or not raw.get("name") or "value" not in raw:
        return None
    domain = str(raw.get("domain") or "vercel.com")
    cookie = {
        "name": str(raw["name"]),
        "value": str(raw["value"]),
        "domain": domain,
        "path": str(raw.get("path") or "/"),
        "secure": bool(raw.get("secure", True)),
        "httpOnly": bool(raw.get("httpOnly", False)),
    }
    exp = raw.get("expiry", raw.get("expirationDate"))
    if isinstance(exp, (int, float)) and exp > 0:
        cookie["expiry"] = int(exp)
    ss = str(raw.get("sameSite") or "").lower()
    cookie["sameSite"] = {
        "strict": "Strict",
        "lax": "Lax",
        "none": "None",
        "no_restriction": "None",
    }.get(ss, "Lax")
    return cookie


def clicar_si_existe(driver, textos):
    for texto in textos:
        for el in driver.find_elements(
            By.XPATH,
            f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{texto}')]"
            f" | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{texto}')]",
        ):
            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                    print("click", texto)
                    return True
            except Exception:
                continue
    return False


def main():
    if not CHROME.exists():
        raise SystemExit("no esta Google Chrome")
    raw = json.loads(COOKIES.read_text(encoding="utf-8"))
    cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
    options = Options()
    options.binary_location = str(CHROME)
    profile = Path(tempfile.mkdtemp(prefix="vercel_chrome_"))
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--window-size=1200,900")
    options.add_argument("--disable-features=msEdgeAccount,msEdgeSync")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(service=Service(), options=options)
    try:
        caps = driver.capabilities or {}
        print("browser", caps.get("browserName"), caps.get("browserVersion"))
        if "edge" in str(caps.get("browserName", "")).lower():
            raise SystemExit("se abrio Edge; se requiere Chrome")
        driver.get("https://vercel.com")
        time.sleep(2)
        ok = 0
        for raw_c in cookies:
            cookie = sanitizar(raw_c)
            if not cookie:
                continue
            try:
                driver.add_cookie(cookie)
                ok += 1
            except Exception:
                cookie.pop("sameSite", None)
                try:
                    driver.add_cookie(cookie)
                    ok += 1
                except Exception:
                    pass
        print("cookies_inyectadas", ok)
        driver.get("https://vercel.com/dashboard")
        time.sleep(4)
        print("dashboard_title", driver.title)
        print("dashboard_url", driver.current_url.split("?")[0])
        if "login" in driver.current_url.lower() or "signup" in driver.current_url.lower():
            clicar_si_existe(driver, ["continue with google", "google"])
            time.sleep(4)
        driver.get(url)
        time.sleep(5)
        print("device_title", driver.title)
        print("device_url", driver.current_url.split("?")[0])
        clicar_si_existe(driver, ["authorize", "confirm", "approve", "allow", "continuar", "confirmar"])
        time.sleep(4)
        clicar_si_existe(driver, ["authorize", "confirm", "approve", "allow", "continuar", "confirmar"])
        for _ in range(20):
            time.sleep(3)
            loc = driver.current_url.lower()
            title = driver.title.lower()
            print("poll_url", loc.split("?")[0], "title", driver.title)
            if any(w in loc or w in title for w in ("success", "approved", "authorized", "dashboard")):
                break
            clicar_si_existe(driver, ["authorize", "confirm", "approve", "allow"])
        print("final_url", driver.current_url.split("?")[0])
        print("final_title", driver.title)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
