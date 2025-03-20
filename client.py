from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneNumberBanned,
    SessionPasswordNeeded
)
import os

class SessionManager:
    def __init__(self):
        self.session_dir = "sessions"
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)

    async def create_client(self, api_id: int, api_hash: str, session_name: str) -> Client:
        try:
            return Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir=self.session_dir,
                in_memory=False,
                app_version="SecureSessionBot/2.0"
            )
        except (ApiIdInvalid, PhoneNumberInvalid) as e:
            raise ValueError(f"Authentication failed: {str(e)}") from e
        except PhoneNumberBanned as e:
            raise RuntimeError(f"Banned number: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Client error: {str(e)}") from e
