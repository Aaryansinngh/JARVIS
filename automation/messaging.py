"""
automation/messaging.py — WhatsApp and Email sending

WhatsApp: Uses pywhatkit (opens WhatsApp Web in browser)
Email: Uses Gmail API with OAuth2 (secure, no password needed)

For WhatsApp to work:
  - Chrome must be installed
  - You must be logged in to web.whatsapp.com at least once

For Gmail to work:
  - Create a Google Cloud project
  - Enable Gmail API
  - Download credentials.json → save to ./credentials/gmail_credentials.json
  - First run will open a browser to authorise
"""
import os
import base64
import time
from email.mime.text import MIMEText
from pathlib import Path
from utils.logger import logger
from utils.config import get


class WhatsAppSender:
    """Send WhatsApp messages via WhatsApp Web."""

    def send(self, contact_name: str, message: str) -> bool:
        """
        Send a WhatsApp message to a contact by name.

        Args:
            contact_name: The contact's name as saved in WhatsApp
            message: The message to send

        Note: This opens WhatsApp Web and types the message.
              The contact must exist in your WhatsApp contacts.
        """
        try:
            import pywhatkit as kit
            logger.info(f"Sending WhatsApp to '{contact_name}': {message[:50]}...")

            # pywhatkit.sendwhatmsg_to_group_instantly also works for groups
            # For phone numbers: kit.sendwhatmsg("+919876543210", message, hour, min)
            # For contact names (search): this approach
            kit.sendwhatmsg_instantly(
                phone_no=contact_name,  # Works with number: "+919876543210"
                message=message,
                wait_time=15,           # Seconds to wait for WhatsApp Web to load
                tab_close=True,         # Close tab after sending
            )
            logger.info("WhatsApp message sent.")
            return True

        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            logger.info("TIP: Make sure you're logged in to web.whatsapp.com first.")
            return False

    def send_by_name(self, name: str, message: str) -> bool:
        """
        Send to a contact by name (not phone number).
        Opens WhatsApp Web, searches for the contact, sends.
        Uses Playwright for more reliable name-based search.
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()

                page.goto("https://web.whatsapp.com")
                logger.info("Waiting for WhatsApp Web to load (scan QR if first time)...")
                page.wait_for_selector('div[title="Search input textbox"]', timeout=60000)

                # Search for contact
                search = page.locator('div[title="Search input textbox"]')
                search.click()
                search.type(name)
                time.sleep(1.5)

                # Click first result
                page.locator(f'span[title="{name}"]').first.click()
                time.sleep(1)

                # Type and send message
                msg_box = page.locator('div[title="Type a message"]')
                msg_box.click()
                msg_box.type(message)
                page.keyboard.press("Enter")
                time.sleep(2)

                logger.info(f"WhatsApp message sent to '{name}'.")
                browser.close()
            return True

        except Exception as e:
            logger.error(f"WhatsApp Playwright send failed: {e}")
            return False


class EmailSender:
    """Send emails via Gmail API (OAuth2 — no password required)."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self):
        self.creds_path = Path(get("email", "credentials_path", "./credentials/gmail_credentials.json"))
        self.token_path = Path(get("email", "token_path", "./credentials/gmail_token.json"))
        self._service = None

    def _authenticate(self):
        """Authenticate with Gmail API. Opens browser on first run."""
        if self._service:
            return

        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None

        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.creds_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found at {self.creds_path}.\n"
                        "See README.md for setup instructions."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.creds_path), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API authenticated.")

    def send(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text email body
        """
        try:
            self._authenticate()

            msg = MIMEText(body)
            msg["to"] = to
            msg["subject"] = subject

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            self._service.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()

            logger.info(f"Email sent to '{to}' — Subject: '{subject}'")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
