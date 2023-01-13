import smtplib, ssl
import app.settings

from email.utils import formatdate, COMMASPACE
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def send_email(receivers: list[str], subject: str, content, attachments: list[MIMEMessage]):
    """Sends an email using the specified SMTP settings in the config with the specified subject, content and attachments to the specified receivers"""
    
    with smtplib.SMTP_SSL(app.settings.SMTP_SERVER, app.settings.SMTP_PORT, context=ssl.create_default_context()) as server:
        server.login(app.settings.SMTP_USERNAME, app.settings.SMTP_PASSWORD)
        
        msg = MIMEMultipart()
        msg['From'] = app.settings.SMTP_EMAIL
        msg['To'] = COMMASPACE.join(receivers)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
        msg.attach(MIMEText(content, "html"))
        
        for attachment in attachments:
            msg.attach(attachment)
            
        server.sendmail(app.settings.SMTP_EMAIL, receivers, msg=msg.as_string())
        
        
def get_file_attachment(filename: str, data: bytes) -> MIMEApplication:
    """Returns the specified bytes with the specified filename as a MIMEApplication attachment."""
    
    attachment = MIMEApplication(data)
    attachment["Content-Disposition"] = f"attachment; filename=\"{filename}\""
    
    return attachment