"""
Email Service for sending PDF reports via email using Mailgun
"""
import os
import re
from typing import Optional
import logging
from dotenv import load_dotenv
import httpx

logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# Mailgun configuration from environment
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY") or os.getenv("EMAIL_API")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
EMAIL_FROM_RAW = os.getenv("EMAIL_FROM")
EMAIL_FROM_NAME_DEFAULT = os.getenv("EMAIL_FROM_NAME", "Synapse")

# Parse EMAIL_FROM if it contains display name format: "Display Name <email@domain.com>"
EMAIL_FROM = EMAIL_FROM_RAW
EMAIL_FROM_NAME = EMAIL_FROM_NAME_DEFAULT

if EMAIL_FROM_RAW:
    # Check if format is "Display Name <email@domain.com>"
    match = re.match(r'^(.+?)\s*<(.+?)>$', EMAIL_FROM_RAW)
    if match:
        # Extract display name and email
        EMAIL_FROM_NAME = match.group(1).strip()
        EMAIL_FROM = match.group(2).strip()
        logger.info(f"Parsed EMAIL_FROM: Display Name='{EMAIL_FROM_NAME}', Email='{EMAIL_FROM}'")

# Mailgun API endpoint
MAILGUN_API_URL = "https://api.mailgun.net/v3"


class EmailService:
    """Service for sending emails with PDF attachments using Mailgun."""
    
    def __init__(self):
        self.api_key = MAILGUN_API_KEY
        self.domain = MAILGUN_DOMAIN
        self.email_from = EMAIL_FROM
        self.email_from_name = EMAIL_FROM_NAME
        self.api_url = f"{MAILGUN_API_URL}/{self.domain}/messages" if self.domain else None
        
        # Log configuration status on initialization
        if self.is_configured():
            logger.info("✅ Mailgun email service configured")
            logger.info(f"   Domain: {self.domain}")
            logger.info(f"   From: {self.email_from_name} <{self.email_from}>")
        else:
            logger.warning("⚠️  Mailgun email service not fully configured")
            logger.warning(f"   API Key: {'✅ Set' if self.api_key else '❌ Missing'}")
            logger.warning(f"   Domain: {'✅ Set' if self.domain else '❌ Missing'}")
            logger.warning(f"   Email From: {'✅ Set' if self.email_from else '❌ Missing'}")
        
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.api_key and self.domain and self.email_from)
    
    async def send_pdf_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        pdf_bytes: bytes,
        pdf_filename: str = "person_profile.pdf",
        person_name: Optional[str] = None
    ) -> dict:
        """
        Send an email with PDF attachment using Mailgun API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            pdf_bytes: PDF file bytes
            pdf_filename: Name for the PDF attachment
            person_name: Optional person name for personalization
            
        Returns:
            dict with success status and message
        """
        if not self.is_configured():
            error_msg = "Email service not configured. Please set MAILGUN_API_KEY (or EMAIL_API), MAILGUN_DOMAIN, and EMAIL_FROM in .env"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        
        try:
            logger.info(f"📧 Sending email via Mailgun to {to_email}...")
            logger.info(f"   Domain: {self.domain}")
            logger.info(f"   API URL: {self.api_url}")
            logger.info(f"   From: {self.email_from_name} <{self.email_from}>")
            logger.info(f"   PDF Size: {len(pdf_bytes)} bytes")
            logger.info(f"   PDF Filename: {pdf_filename}")
            
            # Prepare form data for Mailgun API
            # Mailgun expects attachments as multipart/form-data
            # Format: files dict with tuple (filename, file_bytes, content_type)
            files = {
                'attachment': (pdf_filename, pdf_bytes, 'application/pdf')
            }
            
            # Extract custom message from body if present
            custom_message = ""
            if "Please find attached" in body:
                parts = body.split("Please find attached")[1].split("This report")
                if len(parts) > 1 and parts[0].strip():
                    custom_message = parts[0].strip()
            
            # Create HTML version of email for better deliverability
            html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin-top: 0;">Profile Report</h2>
        <p style="margin-bottom: 0;">Hello,</p>
    </div>
    
    <div style="background-color: #ffffff; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px; margin-bottom: 20px;">
        <p>Please find attached the profile report for <strong>{person_name or 'the requested person'}</strong>.</p>
        {f'<p style="margin-top: 15px; padding: 10px; background-color: #f0f0f0; border-left: 3px solid #3498db;">{custom_message}</p>' if custom_message else ''}
        <p style="margin-top: 20px;">This report was generated using AI technology and includes comprehensive information about {person_name or 'the requested person'}.</p>
    </div>
    
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; font-size: 12px; color: #666;">
        <p style="margin: 0;">Best regards,<br><strong>{self.email_from_name}</strong></p>
        <p style="margin-top: 10px; margin-bottom: 0; font-size: 11px; color: #999;">
            This is an automated email. Please do not reply to this message.
        </p>
    </div>
</body>
</html>"""
            
            # Mailgun API form data with anti-spam headers
            data = {
                'from': f"{self.email_from_name} <{self.email_from}>",
                'to': to_email,
                'subject': subject,
                'text': body,  # Plain text version
                'html': html_body,  # HTML version for better deliverability
                # Anti-spam headers
                'h:Reply-To': self.email_from,  # Proper Reply-To header
                'h:X-Mailer': 'Synapse',  # Identify sender
                'h:Precedence': 'bulk',  # Mark as transactional
                'h:List-Unsubscribe': f'<mailto:{self.email_from}?subject=unsubscribe>',  # Unsubscribe option
                'o:tag': 'pdf-report',  # Tag for tracking
                'o:tracking': 'yes',  # Enable tracking
                'o:tracking-clicks': 'no',  # Disable click tracking (can trigger spam)
                'o:tracking-opens': 'no',  # Disable open tracking (can trigger spam)
                'o:require-tls': 'true',  # Require TLS encryption
                'o:skip-verification': 'false',  # Verify domain
            }
            
            # Send email via Mailgun API
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(f"   Sending POST request to Mailgun API...")
                response = await client.post(
                    self.api_url,
                    auth=("api", self.api_key),
                    data=data,
                    files=files
                )
                
                logger.info(f"   Response Status: {response.status_code}")
                
                # Check for errors
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"   Error Response: {error_text}")
                    raise httpx.HTTPStatusError(
                        f"Mailgun API returned {response.status_code}",
                        request=response.request,
                        response=response
                    )
                
                result = response.json()
                
                logger.info(f"✅ Email sent successfully to {to_email}")
                logger.info(f"   Message ID: {result.get('id', 'N/A')}")
                logger.info(f"   Message: {result.get('message', 'N/A')}")
                
                return {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                    "to": to_email,
                    "message_id": result.get('id'),
                    "mailgun_message": result.get('message')
                }
            
        except httpx.HTTPStatusError as e:
            try:
                error_detail = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else e.response.text
            except:
                error_detail = e.response.text
            
            error_msg = f"Mailgun API error ({e.response.status_code}): {error_detail}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   Request URL: {self.api_url}")
            logger.error(f"   Domain: {self.domain}")
            logger.error(f"   API Key Set: {bool(self.api_key)}")
            
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        except httpx.RequestError as e:
            error_msg = f"Failed to connect to Mailgun API: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.error(f"   API URL: {self.api_url}")
            logger.error(f"   Check your internet connection and Mailgun service status")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            import traceback
            logger.error(f"❌ {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": error_msg
            }
    
    async def send_text_email(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> dict:
        """
        Send a plain text/HTML email using Mailgun API.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text (plain text)

        Returns:
            dict with success status and message
        """
        if not self.is_configured():
            error_msg = "Email service not configured. Please set MAILGUN_API_KEY (or EMAIL_API), MAILGUN_DOMAIN, and EMAIL_FROM in .env"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

        try:
            html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
        <h2 style="color: #2c3e50; margin-top: 0;">Synapse</h2>
    </div>
    <div style="background-color: #ffffff; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px; margin-bottom: 20px; white-space: pre-wrap;">
{body}
    </div>
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; font-size: 12px; color: #666;">
        <p style="margin: 0;">Best regards,<br><strong>{self.email_from_name}</strong></p>
    </div>
</body>
</html>"""

            data = {
                'from': f"{self.email_from_name} <{self.email_from}>",
                'to': to_email,
                'subject': subject,
                'text': body,
                'html': html_body,
                'h:Reply-To': self.email_from,
                'o:tag': 'text-message',
                'o:tracking': 'no',
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    auth=("api", self.api_key),
                    data=data,
                )

                if response.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"Mailgun API returned {response.status_code}",
                        request=response.request,
                        response=response
                    )

                result = response.json()
                logger.info(f"✅ Text email sent to {to_email}")
                return {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                    "to": to_email,
                    "message_id": result.get('id'),
                }

        except httpx.HTTPStatusError as e:
            try:
                error_detail = e.response.json() if e.response.headers.get("content-type", "").startswith("application/json") else e.response.text
            except Exception:
                error_detail = e.response.text
            error_msg = f"Mailgun API error ({e.response.status_code}): {error_detail}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg, "status_code": e.response.status_code}
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    def get_configuration_status(self) -> dict:
        """Get email service configuration status."""
        return {
            "configured": self.is_configured(),
            "service": "Mailgun",
            "domain": self.domain,
            "email_from": self.email_from,
            "email_from_name": self.email_from_name,
            "api_key_set": bool(self.api_key),
            "domain_set": bool(self.domain),
            "email_from_set": bool(self.email_from),
        }

