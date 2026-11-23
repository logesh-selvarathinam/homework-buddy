"""App settings. Fill in SUPABASE_URL and SUPABASE_ANON_KEY before building.

The anon key is safe to ship inside the app: Row Level Security in
supabase/schema.sql decides what each signed-in phone can read and write.
Never put the service-role key here.
"""
import os

SUPABASE_URL = os.getenv("HB_SUPABASE_URL", "https://YOUR-PROJECT.supabase.co")
SUPABASE_ANON_KEY = os.getenv("HB_SUPABASE_ANON_KEY", "YOUR-ANON-KEY")

# In-app update: the app reads this file to see if a newer APK exists.
# The GitHub build workflow attaches it to each GitHub Release of this repo
# (the repo must be public so phones can download it).
GITHUB_REPO = "logesh-selvarathinam/homework-buddy"
UPDATE_MANIFEST_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/latest.json"

IMAGE_BUCKET = "homework-images"

# Reminders
EVENING_REMINDER_HOUR = 19      # 7 pm, the evening before homework is due
SCHOOL_DAYS = {0, 1, 2, 3, 4, 5}  # Mon–Sat (date.weekday(): 0 = Mon)

# Local data folder (Flet sets FLET_APP_STORAGE_DATA inside the built app)
DATA_DIR = os.getenv("FLET_APP_STORAGE_DATA") or os.path.join(os.getcwd(), "local_data")

CHILD_COLORS = ["#C2410C", "#0F766E", "#7C3AED", "#BE185D"]

SUBJECT_COLORS = {
    "Maths": ("#DBEAFE", "#1E40AF"),
    "English": ("#FCE7F3", "#9D174D"),
    "Tamil": ("#FEF3C7", "#92400E"),
    "Hindi": ("#FFE4E6", "#9F1239"),
    "EVS": ("#DCFCE7", "#166534"),
    "Social": ("#E0E7FF", "#3730A3"),
    "Science": ("#CFFAFE", "#155E75"),
}
DEFAULT_SUBJECT_COLOR = ("#EEF0F5", "#3F4455")
