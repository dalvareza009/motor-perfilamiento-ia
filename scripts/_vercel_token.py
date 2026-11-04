import json
import os
from pathlib import Path

src = Path(r"c:\Users\daniela.alvarez\Downloads\vercel.com_cookies.json")
raw = json.loads(src.read_text(encoding="utf-8"))
cookies = raw.get("cookies", raw) if isinstance(raw, dict) else raw
auth = next((c.get("value") for c in cookies if isinstance(c, dict) and c.get("name") == "authorization"), None)
if not auth:
    raise SystemExit("no authorization cookie")
if auth.lower().startswith("bearer "):
    auth = auth[7:]
out = Path(os.environ["TEMP"]) / "vercel_token.txt"
out.write_text(auth, encoding="utf-8")
print("token_chars", len(auth))
print("token_kind", "jwt" if auth.count(".") == 2 else "other")
