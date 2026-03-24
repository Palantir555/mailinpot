"""
mailflow – app-agnostic inbound email client for mailinpot.

Typical usage::

    from mailflow.addressing import generate_recipient
    from mailflow.client import MailflowClient
    from mailflow.wait import wait_for_email

    client = MailflowClient(base_url="https://mailinpot.example.com", api_secret="…")
    recipient = generate_recipient(prefix="run")
    email = wait_for_email(client, recipient, timeout=60)
    print(email.subject, email.body_text)
"""

from mailflow.client import MailflowClient
from mailflow.models import Email
from mailflow.wait import wait_for_email

__all__ = ["MailflowClient", "Email", "wait_for_email"]
