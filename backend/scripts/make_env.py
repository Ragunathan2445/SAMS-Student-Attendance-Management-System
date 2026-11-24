"""Create backend/.env from .env.example with freshly generated secrets.

    python -m scripts.make_env              # refuses to overwrite an existing .env
    python -m scripts.make_env --force
"""
import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

backend = Path(__file__).resolve().parents[1]
target = backend / ".env"
if target.exists() and "--force" not in sys.argv:
    raise SystemExit(".env already exists (use --force to overwrite).")

text = (backend / ".env.example").read_text(encoding="utf-8")
text = text.replace("SECRET_KEY=replace-with-a-long-random-string-of-at-least-32-characters",
                    f"SECRET_KEY={secrets.token_urlsafe(48)}")
text = text.replace("TOTP_ENCRYPTION_KEY=", f"TOTP_ENCRYPTION_KEY={Fernet.generate_key().decode()}", 1)
target.write_text(text, encoding="utf-8")
print(f"Wrote {target} with new random secrets. Edit DATABASE_URL if your PostgreSQL credentials differ.")
