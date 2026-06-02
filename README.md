# Google Account Data Exporter

Export **all** your Google data (Gmail, Drive, Calendar, YouTube, Contacts) from multiple accounts — faster than Google Takeout. Designed to run in **Termux on Android**, but works anywhere Python runs.

## Features

- **Multi-account** — export from as many Gmail accounts as you want
- **Resumable** — interrupted? just run it again, picks up where it left off
- **Rate-limit safe** — exponential backoff with jitter, won't get you banned
- **Two Gmail modes** — fast metadata-only (JSON) or full emails (.eml)
- **2FA compatible** — uses real Google OAuth browser login
- **Selective export** — choose which services to export
- **Progress tracking** — see how much was exported per account

## What Gets Exported

| Service | What you get |
|---------|-------------|
| **Gmail** | All emails as `.eml` files (or metadata JSON), labels |
| **Drive** | All files, Google Docs exported as `.docx`/`.xlsx`/`.pptx` |
| **Calendar** | All calendars with all events |
| **YouTube** | Playlists, liked videos, subscriptions, uploads metadata |
| **Contacts** | All contacts with names, emails, phones, addresses |

## Prerequisites

### 1. Google Cloud Project (one-time, ~10 min)

You need a `credentials.json` file from Google. Here's the fastest path:

#### Option A: Using `gcloud` CLI (recommended)

```bash
# Install gcloud (skip if already installed)
# Termux: pkg install google-cloud-sdk
# Mac/Linux: curl https://sdk.cloud.google.com | bash

gcloud auth login
gcloud projects create my-data-export --set-as-default

# Enable all APIs at once
gcloud services enable \
  gmail.googleapis.com \
  drive.googleapis.com \
  calendar-json.googleapis.com \
  youtube.googleapis.com \
  people.googleapis.com
```

Then open this URL to create the OAuth credentials:
```
https://console.cloud.google.com/apis/credentials?project=my-data-export
```

- Click **Create Credentials** → **OAuth Client ID**
- If prompted, configure consent screen: **External** → fill in app name → add your email → save
- Application type: **Desktop App**
- Download the JSON → rename to `credentials.json` → place in this directory

#### Option B: Full manual steps

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (any name)
3. Go to **APIs & Services** → **Library**
4. Search and enable: Gmail API, Google Drive API, Google Calendar API, YouTube Data API v3, People API
5. Go to **APIs & Services** → **OAuth consent screen**
   - User type: **External**
   - Fill in app name and your email
   - Add scopes: `gmail.readonly`, `drive.readonly`, `calendar.readonly`, `youtube.readonly`, `contacts.readonly`
   - Add yourself as a test user
6. Go to **APIs & Services** → **Credentials**
   - Create Credentials → OAuth Client ID → Desktop App
   - Download JSON → rename to `credentials.json`

### 2. Install Python dependencies

```bash
# Termux
pkg update && pkg install python git
pip install -r requirements.txt

# Mac/Linux/Windows
pip install -r requirements.txt
```

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/google-data-exporter.git
cd google-data-exporter

# 2. Add your credentials.json (see Prerequisites above)

# 3. List your accounts
nano accounts.txt
# Add one email per line:
#   myemail@gmail.com
#   oldemail@gmail.com

# 4. Authenticate (one-time per account — opens browser)
python main.py setup

# 5. Export everything
python main.py export
```

## Usage

### Authenticate accounts

```bash
python main.py setup
```

Opens a browser for each account in `accounts.txt`. Login with the correct account (use incognito if needed). Handles 2FA, passkeys, etc. — it's a real Google login page.

**Tokens are saved in `tokens/` and last indefinitely** unless you revoke them or don't use them for 6 months.

### Export data

```bash
# Export everything (full .eml emails — thorough but slower)
python main.py export

# Fast mode — metadata only for Gmail (subject, from, date, snippet as JSON)
python main.py export --gmail-mode metadata

# Export only specific services
python main.py export --services gmail,contacts
python main.py export --services drive

# Custom output directory
python main.py export --output /sdcard/backup

# Verbose logging (debug API issues)
python main.py -v export
```

### Check progress

```bash
python main.py status
```

Shows how many items have been exported per service per account.

### Resume after interruption

Just run the same export command again. The tool tracks every item it has exported and skips them on the next run.

```bash
# Phone died at email 3,000 of 15,000? Just run again:
python main.py export
# → Picks up at email 3,001
```

## Output Structure

```
exports/
├── myemail@gmail.com/
│   ├── gmail/
│   │   ├── labels.json
│   │   ├── emails_metadata.json    # (if metadata mode)
│   │   └── eml/                    # (if full mode)
│   │       ├── 18f2a3b4c5d6e7f8.eml
│   │       └── ...
│   ├── drive/
│   │   ├── file_listing.json
│   │   ├── My Document.docx
│   │   └── ...
│   ├── calendar/
│   │   ├── Personal.json
│   │   └── Work.json
│   ├── youtube/
│   │   ├── channels.json
│   │   ├── playlists.json
│   │   ├── liked_videos.json
│   │   ├── subscriptions.json
│   │   └── uploads.json
│   ├── contacts/
│   │   └── contacts.json
│   └── .progress/                  # resume tracking
│       ├── gmail.json
│       ├── drive.json
│       └── ...
└── oldemail@gmail.com/
    └── ...
```

## Termux Tips

- **Install from F-Droid**, not Play Store (Play Store version is outdated)
- **Prevent Android from killing the process**: `termux-wake-lock` before running
- **Large exports**: If your mailbox is huge (50k+ emails), start with `--gmail-mode metadata` to get the fast overview, then run again with `--gmail-mode full` for complete emails
- **Storage**: Exports go to Termux's internal storage by default. To save to shared storage: `python main.py export -o /sdcard/google-export`
- **Background**: Use `tmux` or `screen` to keep the session alive if you switch apps:
  ```bash
  pkg install tmux
  tmux
  python main.py export
  # Press Ctrl+B, then D to detach
  # Reattach later: tmux attach
  ```

## Known Limitations

- **YouTube videos cannot be downloaded** — the API only provides metadata. For actual video files, use `yt-dlp` separately
- **Google Photos API** is restricted for new apps — not included
- **Google Keep** has no public API
- **Large Drive files** may time out on slow connections
- **OAuth consent screen** — if you add other users' accounts (not just yours), you'll need to submit your app for Google verification

## Security

- Your Google password is **never** stored or seen by this tool
- Only OAuth tokens are saved (in `tokens/` — keep these private!)
- `tokens/` and `exports/` are in `.gitignore` — they won't be pushed to GitHub
- Tokens can be revoked at any time at https://myaccount.google.com/permissions

## License

MIT
