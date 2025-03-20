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
import time

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Comprehensive session management with:
    - Secure session storage
    - Credentials validation
    - Session revocation
    - Auto-cleanup of old sessions
    """
    
    def __init__(self):
        self.session_dir = "sessions"
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        """Create secure session storage directory"""
        try:
            if not os.path.exists(self.session_dir):
                os.makedirs(self.session_dir, mode=0o700)
                logger.info(f"Created secure session directory: {self.session_dir}")
        except Exception as e:
            logger.error(f"Directory creation failed: {str(e)}")
            raise RuntimeError("Session storage initialization failed") from e

    async def create_client(self, api_id: int, api_hash: str, user_id: int) -> Client:
        """
        Creates and validates a Pyrogram client
        
        Args:
            api_id: Valid Telegram API ID
            api_hash: Valid Telegram API Hash
            user_id: Telegram user ID for session isolation
            
        Returns:
            Authenticated Pyrogram Client instance
            
        Raises:
            ValueError: For invalid credentials
            RuntimeError: For session creation failures
        """
        session_name = f"session_{user_id}"
        
        try:
            client = Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir=self.session_dir,
                in_memory=False,
                app_version="SecureSessionBot/4.0"
            )
            
            # Pre-validate credentials
            await client.connect()
            await client.disconnect()
            return client
            
        except (ApiIdInvalid, PhoneNumberInvalid) as e:
            logger.error(f"Invalid API credentials: {str(e)}")
            raise ValueError(f"Invalid API credentials: {str(e)}") from e
        except Exception as e:
            logger.error(f"Client creation failed: {str(e)}")
            raise RuntimeError(f"Session creation failed: {str(e)}") from e

    async def revoke_session(self, user_id: int):
        """Terminate and delete a user's session"""
        try:
            session_file = os.path.join(self.session_dir, f"session_{user_id}.session")
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Revoked session for user: {user_id}")
        except Exception as e:
            logger.error(f"Session revocation failed: {str(e)}")
            raise RuntimeError("Session revocation failed") from e

    async def cleanup_old_sessions(self, max_age_days: int = 30):
        """Automatically remove inactive sessions older than specified days"""
        try:
            cutoff_time = time.time() - (max_age_days * 86400)
            for session_file in os.listdir(self.session_dir):
                file_path = os.path.join(self.session_dir, session_file)
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    logger.info(f"Cleaned up old session: {session_file}")
        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}")
            raise RuntimeError("Session cleanup operation failed") from e
