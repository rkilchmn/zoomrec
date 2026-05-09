"""
Email Sending Module

This module provides functionality to send emails using SMTP.
It supports sending plain text and HTML emails with attachments.
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
import logging

# Configure logging - use root logger to inherit from calling module (e.g., gunicorn)
logger = logging.getLogger()

class EmailSender:
    """
    A class to handle email sending functionality.
    
    Configuration is done through environment variables:
    - SMTP_SERVER: SMTP server address (e.g., 'smtp.gmail.com')
    - SMTP_PORT: SMTP server port (default: 587 for TLS)
    - SMTP_USERNAME: Email username
    - SMTP_PASSWORD: Email password or app password
    - SMTP_USE_TLS: Use TLS (True/False, default: True)
    - SMTP_USE_SSL: Use SSL (True/False, default: False)
    - EMAIL_FROM: Default 'From' email address
    - EMAIL_FROM_NAME: Default 'From' name
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the EmailSender with configuration.
        
        Args:
            config: Optional configuration dictionary that overrides environment variables.
                   Can include: smtp_server, smtp_port, smtp_username, smtp_password,
                   use_tls, use_ssl, email_from, email_from_name.
        """
        self.config = {
            'smtp_server': os.getenv('SMTP_SERVER', ''),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_username': os.getenv('SMTP_USERNAME', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            'use_ssl': os.getenv('SMTP_USE_SSL', 'false').lower() == 'true',
            'email_from': os.getenv('EMAIL_FROM', ''),
            'email_from_name': os.getenv('EMAIL_FROM_NAME', '')
        }
        
        # Override with provided config
        if config:
            self.config.update({k: v for k, v in config.items() if v is not None})
    
    def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        cc: Optional[Union[str, List[str]]] = None,
        bcc: Optional[Union[str, List[str]]] = None,
        attachments: Optional[List[Union[str, bytes, tuple]]] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Send an email with optional HTML content and attachments.
        
        Args:
            to_emails: Email address or list of email addresses to send to
            subject: Email subject
            body: Plain text email body
            body_html: Optional HTML email body
            from_email: Sender email address (defaults to EMAIL_FROM from config)
            from_name: Sender name (defaults to EMAIL_FROM_NAME from config)
            cc: CC email address or list of CC email addresses
            bcc: BCC email address or list of BCC email addresses
            attachments: List of file paths or (filename, content, mime_type) tuples
            reply_to: Reply-to email address
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        # Validate required parameters
        if not self.config['smtp_server'] or not self.config['smtp_username']:
            logger.error("SMTP server or username not configured")
            return False
            
        if not to_emails:
            logger.error("No recipient email addresses provided")
            return False
            
        # Convert single email to list
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        if cc and isinstance(cc, str):
            cc = [cc]
        if bcc and isinstance(bcc, str):
            bcc = [bcc]
            
        # Set default from email/name if not provided
        from_email = from_email or self.config['email_from']
        from_name = from_name or self.config['email_from_name']
        
        if not from_email:
            logger.error("No sender email address provided")
            return False
        
        try:
            # Create message container
            # Use nested structure for HTML emails with attachments:
            # - Root: multipart/mixed
            #   - Part 1: multipart/alternative (text + HTML)
            #   - Part 2+: attachments
            if attachments or body_html:
                msg = MIMEMultipart('mixed')
            else:
                msg = MIMEMultipart('plain')
            msg['Subject'] = subject
            msg['From'] = formataddr((from_name, from_email)) if from_name else from_email
            msg['To'] = ', '.join(to_emails)

            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            if reply_to:
                msg['Reply-To'] = reply_to

            # Attach the body (text and HTML as alternative representations)
            if body_html:
                # Use multipart/alternative for text + HTML
                alternative_part = MIMEMultipart('alternative')
                alternative_part.attach(MIMEText(body, 'plain'))
                alternative_part.attach(MIMEText(body_html, 'html'))
                msg.attach(alternative_part)
            else:
                # Just plain text
                msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    if isinstance(attachment, tuple) and len(attachment) == 3:
                        # Attachment as (filename, content, mime_type)
                        filename, content, mime_type = attachment
                        if isinstance(content, str):
                            content = content.encode('utf-8')
                        part = MIMEApplication(content, _subtype=mime_type.split('/')[-1])
                    else:
                        # Attachment as file path
                        file_path = str(attachment)
                        filename = os.path.basename(file_path)
                        with open(file_path, 'rb') as f:
                            part = MIMEApplication(f.read())

                    part.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(part)
            
            # Combine all recipients
            all_recipients = to_emails.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Connect to SMTP server and send email
            context = ssl.create_default_context()
            
            if self.config['use_ssl']:
                with smtplib.SMTP_SSL(
                    self.config['smtp_server'],
                    self.config['smtp_port'],
                    context=context
                ) as server:
                    if self.config['smtp_username'] and self.config['smtp_password']:
                        server.login(self.config['smtp_username'], self.config['smtp_password'])
                    server.send_message(msg)
            else:
                with smtplib.SMTP(
                    self.config['smtp_server'],
                    self.config['smtp_port']
                ) as server:
                    if self.config['use_tls']:
                        server.starttls(context=context)
                    if self.config['smtp_username'] and self.config['smtp_password']:
                        server.login(self.config['smtp_username'], self.config['smtp_password'])
                    server.send_message(msg)
            
            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return False

def send_email(
    to_emails: Union[str, List[str]],
    subject: str,
    body: str,
    **kwargs
) -> bool:
    """
    Convenience function to send an email using default configuration.
    
    Args:
        to_emails: Email address or list of email addresses to send to
        subject: Email subject
        body: Email body (plain text)
        **kwargs: Additional arguments to pass to EmailSender.send_email()
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    sender = EmailSender()
    return sender.send_email(to_emails, subject, body, **kwargs)

# Example usage
if __name__ == "__main__":
    # Example 1: Simple text email
    send_email(
        to_emails="recipient@example.com",
        subject="Test Email",
        body="This is a test email from the EmailSender module."
    )
    
    # Example 2: HTML email with attachment
    html_content = """
    <html>
      <body>
        <h1>Hello!</h1>
        <p>This is a <strong>test email</strong> with HTML content.</p>
      </body>
    </html>
    """
    
    sender = EmailSender({
        'smtp_server': 'smtp.example.com',
        'smtp_port': 587,
        'smtp_username': 'your_username',
        'smtp_password': 'your_password',
        'email_from': 'sender@example.com',
        'email_from_name': 'Sender Name'
    })
    
    sender.send_email(
        to_emails=["recipient1@example.com", "recipient2@example.com"],
        cc="cc@example.com",
        subject="Test Email with Attachment",
        body="Please see the attached file.",
        body_html=html_content,
        attachments=[
            "/path/to/file.pdf",  # File path
            ("example.txt", b"This is the file content", "text/plain")  # (filename, content, mime_type)
        ]
    )
