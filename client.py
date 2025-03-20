from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneNumberBanned,
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired
)
import os
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages Pyrogram client sessions with enhanced error handling and security.
    """

    def __init__(self):
        self.session_dir = "sessions"
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        """Create sessions directory if it doesn't exist."""
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
            logger.info(f"Created session directory: {self.session_dir}")

    async def create_client(self, api_id: int, api_hash: str, session_name: str) -> Client:
        """
        Creates a Pyrogram client with proper error handling.

        Args:
            api_id (int): Telegram API ID.
            api_hash (str): Telegram API hash.
            session_name (str): Unique session identifier.

        Returns:
            Client: Pyrogram client instance.

        Raises:
            ValueError: If API credentials are invalid.
            RuntimeError: If session creation fails.
        """
        try:
            client = Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir=self.session_dir,
                in_memory=False,  # Persist session to disk
                app_version="SecureSessionBot/2.0"
            )
            logger.info(f"Client created for session: {session_name}")
            return client
        except (ApiIdInvalid, PhoneNumberInvalid) as e:
            logger.error(f"Invalid API credentials: {str(e)}")
            raise ValueError(f"Invalid API credentials: {str(e)}") from e
        except PhoneNumberBanned as e:
            logger.error(f"Banned phone number: {str(e)}")
            raise RuntimeError(f"Banned phone number: {str(e)}") from e
        except Exception as e:
            logger.error(f"Client creation failed: {str(e)}")
            raise RuntimeError(f"Client creation failed: {str(e)}") from e

    async def validate_session(self, client: Client) -> bool:
        """
        Validates if the session is active and working.

        Args:
            client (Client): Pyrogram client instance.

        Returns:
            bool: True if session is valid, False otherwise.
        """
        try:
            await client.connect()
            await client.get_me()
            return True
        except Exception as e:
            logger.error(f"Session validation failed: {str(e)}")
            return False
        finally:
            await client.disconnect()
