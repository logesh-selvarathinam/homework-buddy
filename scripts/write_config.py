"""Used by the GitHub build: puts the Supabase URL and anon key into config.py."""
import os
import pathlib
import sys

url = (os.environ.get("HB_SUPABASE_URL") or "").strip()
key = (os.environ.get("HB_SUPABASE_ANON_KEY") or "").strip()
if not url or not key:
    sys.exit("::error::Secret SUPABASE_URL or SUPABASE_ANON_KEY is empty or missing.")
if not url.startswith("https://"):
    sys.exit("::error::SUPABASE_URL must look like https://xxxx.supabase.co")

path = pathlib.Path(__file__).resolve().parent.parent / "src" / "hb" / "config.py"
text = path.read_text(encoding="utf-8")
text = text.replace('"https://YOUR-PROJECT.supabase.co"', repr(url.rstrip("/")))
text = text.replace('"YOUR-ANON-KEY"', repr(key))
path.write_text(text, encoding="utf-8")
print("config.py updated for", url)
