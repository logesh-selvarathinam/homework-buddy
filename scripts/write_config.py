"""Used by the GitHub build: puts the Supabase URL and anon key into config.py."""
import os
import pathlib
import sys

url = (os.environ.get("HB_SUPABASE_URL") or "").strip()
key = (os.environ.get("HB_SUPABASE_ANON_KEY") or "").strip()
if not url or not key:
    sys.exit("::error::Secret SUPABASE_URL or SUPABASE_ANON_KEY is empty or missing.")
from urllib.parse import urlparse

u = urlparse(url)
if u.scheme != "https" or not u.netloc:
    sys.exit("::error::SUPABASE_URL must look like https://xxxx.supabase.co")
if u.path.strip("/"):
    print(f"Note: removed '{u.path}' from SUPABASE_URL; only https://{u.netloc} is used.")
url = f"https://{u.netloc}"

path = pathlib.Path(__file__).resolve().parent.parent / "src" / "hb" / "config.py"
text = path.read_text(encoding="utf-8")
text = text.replace('"https://YOUR-PROJECT.supabase.co"', repr(url))
text = text.replace('"YOUR-ANON-KEY"', repr(key))
path.write_text(text, encoding="utf-8")
print("config.py updated for", u.netloc.split(".")[0][:4] + "…supabase.co")
