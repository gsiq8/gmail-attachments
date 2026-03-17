import os
import re
import base64
import zipfile
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, unquote
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import CREDENTIALS_PATH, TOKEN_PATH

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def extract_download_links(html_body):
    """Extract CloudFront download URLs from ShipHero email body."""
    pattern = r'href="(https://[^"]*cloudfront\.net/[^"]*\.csv)"'
    return re.findall(pattern, html_body)

def get_email_body(message):
    """Extract the email body (HTML or plain text) from a Gmail message."""
    payload = message['payload']

    # Single-part message
    if 'body' in payload and payload['body'].get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

    # Multi-part message
    for part in payload.get('parts', []):
        if part['mimeType'] in ('text/html', 'text/plain') and part['body'].get('data'):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')

    return ''

def download_and_zip(service):
    os.makedirs(TEMP_DIR, exist_ok=True)
    downloaded = []

    today = datetime.now().strftime('%Y/%m/%d')
    query = f'from:noreply@shiphero.com newer_than:1h'
    print(f"Query: {query}")

    results = service.users().messages().list(
        userId='me', q=query, maxResults=500
    ).execute()

    messages = results.get('messages', [])
    print(f"Found {len(messages)} emails")

    if not messages:
        print("No emails matched. Check that emails arrived today and sender matches exactly.")
        return

    for msg in messages:
        message = service.users().messages().get(
            userId='me', id=msg['id']
        ).execute()

        headers = {h['name']: h['value'] for h in message['payload']['headers']}
        subject = headers.get('Subject', 'No Subject')

        body = get_email_body(message)
        links = extract_download_links(body)

        if not links:
            print(f"  ⚠ No download link found in: '{subject}'")
            continue

        for url in links:
            # Extract filename from URL
            path = urlparse(url).path
            filename = unquote(os.path.basename(path))

            filepath = os.path.join(TEMP_DIR, filename)

            # Avoid overwriting duplicates
            if os.path.exists(filepath):
                base, ext = os.path.splitext(filename)
                filepath = os.path.join(TEMP_DIR, f"{base}_{msg['id'][:6]}{ext}")

            # Download the file
            response = requests.get(url)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                downloaded.append(filepath)
                print(f"  ✓ Downloaded: {filename}  (from: '{subject}')")
            else:
                print(f"  ✗ Failed to download {filename}: HTTP {response.status_code}")

    if not downloaded:
        print("No files downloaded.")
        return

    # Pack everything into a single zip
    with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filepath in downloaded:
            zf.write(filepath, arcname=os.path.basename(filepath))

    # Cleanup temp files
    for filepath in downloaded:
        os.remove(filepath)
    os.rmdir(TEMP_DIR)

    print(f"\nDone. {len(downloaded)} file(s) zipped → {os.path.abspath(OUTPUT_ZIP)}")

service = authenticate_gmail()
download_and_zip(service)