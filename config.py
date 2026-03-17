import os
from pathlib import Path

CREDENTIALS_PATH = Path(
    os.getenv("GOOGLE_OAUTH_CREDENTIALS", str(Path.home() / ".config/gmail-attachments/credentials.json"))
)
TOKEN_PATH = Path(
    os.getenv("GOOGLE_OAUTH_TOKEN", str(Path.home() / ".config/gmail-attachments/token.json"))
)