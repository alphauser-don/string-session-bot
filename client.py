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
from typing import Optional

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Comprehensive session management with enhanced security and error handling
    Features:
    - Session persistence
    - Input validation
    - Error tracking
    - Auto-clean capabilities
    - Session validation
    """

    def __init__(self):
        self.session_dir = "sessions"
        self._ensure_session_dir()
        self.active_sessions = {}

    def _ensure_session_dir(self):
        """Create secure session storage directory"""
        try:
            if not os.path.exists(self.session_dir):
                os.makedirs(self.session_dir, mode=0o700)
                logger.info(f"Created secure session directory: {self.session_dir}")
        except Exception as e:
            logger.error(f"Directory creation failed: {str(e)}")
            raise RuntimeError("Session storage initialization failed") from e

    async def create_client(
        self,
        api_id: int,
        api_hash: str,
        user_id: int
    ) -> Client:
        """
        Creates and validates a Pyrogram client with comprehensive error handling
        
        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API HASH from my.telegram.org
            user_id: Telegram user ID for session isolation
            
        Returns:
            Authenticated Pyrogram Client instance
            
        Raises:
            AuthError: For authentication-related failures
            SessionError: For session management issues
        """
        session_name = f"session_{user_id}"
        
        try:
            client = Client(
                name=session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir=self.session_dir,
                in_memory=False,
                app_version="SecureSessionBot/3.0",
                system_version="SecurityHardened/1.0"
            )
            
            # Validate credentials before returning client
            if not await self._validate_credentials(client):
                raise ValueError("Invalid API credentials")
                
            self.active_sessions[user_id] = client
            return client
            
        except (ApiIdInvalid, PhoneNumberInvalid) as e:
            logger.error(f"Auth error: {str(e)}")
            raise AuthError(f"Authentication failed: {str(e)}") from e
        except PhoneNumberBanned as e:
            logger.error(f"Banned number: {str(e)}")
            raise AuthError("This phone number is banned") from e
        except Exception as e:
            logger.error(f"Session error: {str(e)}")
            raise SessionError(f"Session creation failed: {str(e)}") from e

    async def _validate_credentials(self, client: Client) -> bool:
        """Validate API credentials before full authentication"""
        try:
            await client.connect()
            return await client.send_code("+0000000000")  # Dummy number for validation
        except Exception as e:
            logger.error(f"Credential validation failed: {str(e)}")
            return False
        finally:
            await client.disconnect()

    async def revoke_session(self, user_id: int):
        """Terminate and remove a session"""
        try:
            if user_id in self.active_sessions:
                await self.active_sessions[user_id].terminate()
                del self.active_sessions[user_id]
                logger.info(f"Revoked session for user: {user_id}")
        except Exception as e:
            logger.error(f"Session revocation failed: {str(e)}")
            raise SessionError("Session termination failed") from e

    async def cleanup_old_sessions(self, max_age_days: int = 30):
        """Remove inactive sessions older than specified days"""
        try:
            for session_file in os.listdir(self.session_dir):
                file_path = os.path.join(self.session_dir, session_file)
                if (time.time() - os.path.getmtime(file_path)) > (max_age_days * 86400):
                    os.remove(file_path)
                    logger.info(f"Cleaned up old session: {session_file}")
        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}")
            raise SessionError("Session cleanup operation failed") from e

class AuthError(Exception):
    """Custom exception for authentication failures"""
    pass

class SessionError(Exception):
    """Custom exception for session management issues"""
    pass
