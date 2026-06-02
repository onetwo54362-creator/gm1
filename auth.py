import os
import json
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/contacts.readonly',
]

TOKENS_DIR = 'tokens'
CREDENTIALS_FILE = 'credentials.json'


def _ensure_tokens_dir():
    Path(TOKENS_DIR).mkdir(exist_ok=True)


def _token_path(email):
    """Generate a safe filename for the token file."""
    safe = email.replace('@', '_at_').replace('.', '_')
    return os.path.join(TOKENS_DIR, f'{safe}.json')


def setup_account(email, credentials_file=CREDENTIALS_FILE):
    """Run OAuth flow for a single account. Opens browser for login + 2FA.

    Works in Termux: run_local_server() starts a localhost server and
    Chrome on Android can redirect to it. If that fails, falls back
    to a manual URL copy-paste flow.
    """
    _ensure_tokens_dir()

    if not os.path.exists(credentials_file):
        logger.error(f"Missing {credentials_file}.")
        print(f"\n\u274c '{credentials_file}' not found!")
        print("   Download it from: https://console.cloud.google.com/apis/credentials")
        print("   Save it in this directory as 'credentials.json'")
        return False

    token_file = _token_path(email)
    if os.path.exists(token_file):
        print(f"\u23ed\ufe0f  Token already exists for {email}")
        response = input("   Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            return True

    print(f"\n\U0001f510 Setting up: {email}")
    print(f"   When the browser opens, log in with: {email}")
    print(f"   Use an incognito/private window if you're logged into a different account")
    input("   Press Enter when ready...")

    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)

    try:
        creds = flow.run_local_server(
            port=0,
            prompt='consent',
            authorization_prompt_message=(
                f'Opening browser for {email}...\n'
                'If it doesn\'t open, copy the URL from above into your browser.'
            ),
        )
    except Exception as e:
        logger.warning(f"Local server failed: {e}. Trying manual flow...")
        print(f"\n\u26a0\ufe0f  Browser redirect didn't work. Using manual flow instead.")

        auth_url, _ = flow.authorization_url(prompt='consent')
        print(f"\n1. Open this URL in your browser:\n   {auth_url}")
        print(f"\n2. Log in with: {email}")
        print("3. After authorizing, copy the FULL URL from the address bar.")
        redirect_response = input("\nPaste the redirect URL here: ").strip()
        flow.fetch_token(authorization_response=redirect_response)
        creds = flow.credentials

    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes) if creds.scopes else SCOPES,
        'email': email,
    }

    with open(token_file, 'w') as f:
        json.dump(token_data, f, indent=2)

    print(f"\u2705 Token saved for {email}")
    return True


def load_credentials(email):
    """Load and refresh credentials for an account."""
    token_file = _token_path(email)

    if not os.path.exists(token_file):
        logger.error(f"No token found for {email}. Run 'python main.py setup' first.")
        return None

    with open(token_file, 'r') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes'),
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_data['token'] = creds.token
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            logger.info(f"Token refreshed for {email}")
        except Exception as e:
            logger.error(f"Failed to refresh token for {email}: {e}")
            print(f"\u274c Token expired for {email}. Run 'python main.py setup' to re-authenticate.")
            return None

    return creds


def list_saved_accounts():
    """List all accounts with saved tokens."""
    _ensure_tokens_dir()
    accounts = []
    for f in os.listdir(TOKENS_DIR):
        if f.endswith('.json'):
            try:
                with open(os.path.join(TOKENS_DIR, f), 'r') as file:
                    data = json.load(file)
                    accounts.append(data.get('email', f.replace('.json', '')))
            except (json.JSONDecodeError, KeyError):
                continue
    return accounts


def load_accounts_file(filepath='accounts.txt'):
    """Load account emails from accounts.txt."""
    if not os.path.exists(filepath):
        return []

    accounts = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                accounts.append(line)
    return accounts
