"""
Webmail & Custom Domain SMTP Client.
Handles connection, authentication, SSL/STARTTLS negotiation, and error recovery.
"""

from email.message import Message
import smtplib
import ssl
import time
from typing import Optional, Tuple


class SMTPClient:
    """
    Robust SMTP client tailored for Webmail (cPanel/DirectAdmin/Custom domain) relays.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        use_tls: bool = False,
        timeout: int = 25,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.use_tls = use_tls
        self.timeout = timeout

    def _open_connection(self) -> smtplib.SMTP:
        """Establish, encrypt, and authenticate an SMTP session."""
        if self.use_ssl:
            ssl_context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ssl_context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            if self.use_tls:
                server.ehlo()
                ssl_context = ssl.create_default_context()
                server.starttls(context=ssl_context)
                server.ehlo()

        if self.username and self.password:
            server.login(self.username, self.password)

        return server

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection and credentials against the Webmail SMTP server.
        Returns (success_boolean, status_message).
        """
        try:
            server = self._open_connection()
            server.quit()
            return True, f"Successfully connected and authenticated with {self.host}:{self.port}"
        except smtplib.SMTPAuthenticationError as e:
            return False, f"Authentication Failed (Check Webmail username & password): {e}"
        except smtplib.SMTPConnectError as e:
            return False, f"Could not connect to {self.host}:{self.port}: {e}"
        except Exception as e:
            return False, f"SMTP Connection error ({type(e).__name__}): {e}"

    def send_email(
        self,
        sender: str,
        recipient: str,
        message: Message,
        max_retries: int = 2
    ) -> Tuple[bool, Optional[str]]:
        """
        Send a MIME message with automatic retry on transient socket drops.
        Returns (success_boolean, error_string_if_failed).
        """
        last_error = None

        for attempt in range(1, max_retries + 1):
            server = None
            try:
                server = self._open_connection()
                server.send_message(message, from_addr=sender, to_addrs=[recipient])
                return True, None
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, ConnectionError) as e:
                last_error = f"Transient connection error (attempt {attempt}/{max_retries}): {e}"
                time.sleep(1.5 * attempt)
            except smtplib.SMTPResponseException as e:
                last_error = f"SMTP error ({e.smtp_code}): {e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else e.smtp_error}"
                # Non-transient errors (e.g. 550 User not found) should not retry repeatedly
                if 500 <= e.smtp_code < 600:
                    break
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                break
            finally:
                if server:
                    try:
                        server.quit()
                    except Exception:
                        pass

        return False, last_error

