import os
import base64
import zipfile
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TEMP_DIR = './shiphero_temp'
OUTPUT_ZIP = f'./shiphero_attachments_{datetime.now().strftime("%Y%m%d")}.zip'

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def download_and_zip(service):
    os.makedirs(TEMP_DIR, exist_ok=True)
    downloaded = []

    today = datetime.now().strftime('%Y/%m/%d')
    query = f'has:attachment from:noreply@shiphero.com after:{today}'
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

        for part in message['payload'].get('parts', []):
            filename = part.get('filename')
            att_id = part.get('body', {}).get('attachmentId')

            if filename and att_id:
                att = service.users().messages().attachments().get(
                    userId='me', messageId=msg['id'], id=att_id
                ).execute()

                data = base64.urlsafe_b64decode(att['data'])
                filepath = os.path.join(TEMP_DIR, filename)

                # Avoid overwriting duplicates
                if os.path.exists(filepath):
                    base, ext = os.path.splitext(filename)
                    filepath = os.path.join(TEMP_DIR, f"{base}_{msg['id'][:6]}{ext}")

                with open(filepath, 'wb') as f:
                    f.write(data)

                downloaded.append(filepath)
                print(f"  ✓ Downloaded: {filename}  (from: '{subject}')")

    if not downloaded:
        print("No attachments found.")
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

service = authenticate()
download_and_zip(service)