import json
import ssl
import urllib.request
from pathlib import Path

p = Path(r"c:\Users\daniela.alvarez\Downloads\vercel.com_cookies.json")
raw = json.loads(p.read_text(encoding="utf-8"))
cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
header = "; ".join(
    f"{c['name']}={c['value']}"
    for c in cookies
    if isinstance(c, dict) and c.get("name") and "value" in c
)
auth = next(
    (c.get("value") for c in cookies if isinstance(c, dict) and c.get("name") == "authorization"),
    "",
)
print("auth_has_percent", "%" in str(auth))
print("auth_has_space", " " in str(auth))
ctx = ssl._create_unverified_context()
req = urllib.request.Request(
    "https://api.vercel.com/v2/user",
    headers={"Cookie": header, "User-Agent": "Mozilla/5.0 motor", "Accept": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        data = json.loads(resp.read().decode())
        u = data.get("user", {})
        print("ok", u.get("username"), "team", u.get("defaultTeamId"))
except urllib.error.HTTPError as e:
    print("fail", e.code, e.read()[:200].decode(errors="replace"))
except Exception as e:
    print("fail", type(e).__name__, str(e)[:200])
