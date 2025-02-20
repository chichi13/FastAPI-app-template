import os

from jinja2 import Environment, FileSystemLoader, select_autoescape
from mailjet_rest import Client

from app.core.config import settings
from app.utils.logger import logger


def render_template(template_path, context):
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(os.path.basename(template_path))
    return template.render(context)


def send_email(subject: str, recipients: list[dict[str, str]], body: str) -> None:
    if settings.is_prod():
        mailjet = Client(
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_API_SECRET), version="v3.1"
        )
        recipients_list = [
            {"Email": recipient["email"], "Name": recipient["name"]}
            for recipient in recipients
        ]
        data = {
            "Messages": [
                {
                    "From": {
                        "Email": settings.EMAIL_SENDER,
                        "Name": settings.EMAIL_SENDER_NAME,
                    },
                    "To": recipients_list,
                    "Subject": subject,
                    "HTMLPart": body,
                }
            ]
        }
        result = mailjet.send.create(data=data)

        logger.info(f"Email sent to {recipients} with subject {subject}")
        logger.debug(f"Email result (code {result.status_code}): {result.json()}")
    else:
        logger.info(f"Email sent to {recipients} with subject {subject}")
        logger.info(f"Email body:\n {body}")
