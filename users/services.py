from django.core.mail import EmailMessage

def send_password_reset_email(to_email: str, reset_link: str):
    message = EmailMessage(
        subject="Reset your password",
        body=f"Click here to reset your password: {reset_link}",
        from_email=None, #back to default from email
        to=[to_email],
    )
    message.esp_extra = {
        "category": "Password Reset",
    }
    message.send()