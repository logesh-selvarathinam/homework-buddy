# HomeworkBuddy

Android app (Python + Flet 1.1.3) for parents to track their children's homework,
shared across the family's phones through Supabase, with in-app updates.

- Paste the teacher's WhatsApp / school-app message → it is split into one item per subject
  (English, Tamil incl. "ப எண்", Hindi L3, EVS, Social…) and the right child is picked automatically
- Diary photos and screenshots attached to homework
- Tick done / checked; overdue list; tests go to an **Exams** tab with countdowns
- **Weekly summary** per child (on time / late / missed, by subject)
- **Same data on every phone**: each phone signs in, joins the family with a 6-digit code
- Works offline; syncs every 20 seconds while open
- Evening reminders (7 pm) before homework and exams
- **In-app update**: every new build shows an "Update available" popup on all phones

## 1. Supabase (once)

1. Create a project at supabase.com (a new one, separate from your other apps).
2. **SQL Editor → New query** → paste `supabase/schema.sql` → **Run**.
3. **Authentication → Sign In / Providers → Email**: switch **Confirm email** off
   (simplest for family use; if you leave it on, each person confirms by email once).
4. **Project Settings → API**: copy the **Project URL**, **anon public key** and **service_role key**.

## 2. Signing key (once — keep it safe)

Android only installs an update when it is signed with the same key as the installed app.
A key (`upload.jks`, alias `upload`) was already generated for this project and given to you
outside the repo, with `ANDROID_KEYSTORE_BASE64.txt` and `ANDROID_KEYSTORE_PASSWORD.txt`.
To make a new one instead, on Windows (needs Java — `winget install Microsoft.OpenJDK.17`):

```powershell
keytool -genkey -v -keystore upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
[Convert]::ToBase64String([IO.File]::ReadAllBytes("upload.jks")) | Set-Content keystore-base64.txt
```

Back up `upload.jks` and its password. If they are lost, phones must uninstall and reinstall.

## 3. GitHub (once)

Create a **public** repo (phones download updates from its Releases; no keys are in the code), push this folder, then **Settings → Secrets and variables → Actions**
and add:

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Project URL |
| `SUPABASE_ANON_KEY` | anon public key |
| `ANDROID_KEYSTORE_BASE64` | contents of `keystore-base64.txt` |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |

## 4. Build and install

```bash
git push origin main:release
```

The **Build APK and publish update** workflow runs (the first build takes ~20 minutes).
Download the APK from the run's **Artifacts**, copy it to each phone and install it
(allow "Install unknown apps" when Android asks).

On each phone: **Create a new account** (own email) → first phone **Create family** →
other phones **Join family** with the code from Family tab → add the children with their subjects.

## 5. Releasing an update

Change the code, then push a higher version tag:

Raise `version` in `pyproject.toml` (e.g. 1.0.1), then:

```bash
git push origin main:release
```

Or **Actions → Build APK and publish update → Run workflow**, where you can type the
"What's new" text and tick **Force everyone to update**.

The workflow creates a GitHub Release with the APK and `latest.json`
(`homeworkbuddy-…-older-phones.apk` is for old 32-bit phones only).
Each phone checks the latest release when the app opens (and from **Family → Check for updates**), shows the
popup, and **Download & install** downloads the APK; tapping the downloaded file installs it
over the old version with all data kept.

## 6. Database updates and photo reading (Set up Supabase workflow)

The **Set up Supabase** workflow applies `supabase/schema.sql` to your project and deploys
the photo-reading function. It runs whenever files in `supabase/` change, or from
**Actions → Set up Supabase → Run workflow**. Add these repository secrets once:

| Secret | Where to get it |
|---|---|
| `SUPABASE_ACCESS_TOKEN` | supabase.com → your avatar → **Account preferences → Access Tokens → Generate new token** |
| `GEMINI_API_KEY` | aistudio.google.com/apikey → **Create API key** (free tier is enough for a family) |

Photo reading: in the app, attach a diary photo or screenshot and tap **✨ Read homework from photo**.
The photo is sent to Google Gemini through your Supabase function; only signed-in family members
can use it. Optional secret `GEMINI_MODEL` (default `gemini-2.5-flash`) is set in Supabase
(Edge Functions → Secrets) if Google retires that model.

## Run on your PC (testing)

```bash
pip install -e ".[dev]"
set HB_SUPABASE_URL=https://xxxx.supabase.co
set HB_SUPABASE_ANON_KEY=your-anon-key
flet run src/main.py
pytest
```

## Project layout

```
src/main.py            entry point
src/hb/parser.py       message → subjects (tested on real school messages)
src/hb/store.py        local SQLite copy (offline)
src/hb/api.py          Supabase over HTTP (auth, tables, storage)
src/hb/sync.py         push/pull between phones
src/hb/updater.py      in-app update check
src/hb/reminders.py    evening reminders
src/hb/stats.py        weekly summary numbers
src/hb/ui/…            screens
supabase/schema.sql    tables, security rules, buckets
.github/workflows/     APK build + update publishing
```

## Known limits

- Sharing straight from WhatsApp into the app isn't possible with Flet yet → copy the
  message, then **Add homework → Paste message**. Save WhatsApp photos to the gallery, then pick them.
- Other phones see changes within ~5 seconds while the app is open, or as soon as it is opened.
