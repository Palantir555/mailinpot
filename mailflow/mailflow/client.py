"""
mailflow.client – HTTP client for a member's og-society vault.

Talks to https://og-society.com (or wherever it's deployed) using a personal
API token minted at /den/tokens, not the old mailinpot Cloudflare Worker.
All requests carry `Authorization: Bearer <api_token>`.

Migration note: og-society requires an address to be *minted* via the API
before anything can arrive for it - the old Worker accepted mail to any
address at the domain on arrival, allowlist permitting. mint_address()
below is the new first step; there is no direct equivalent of the old
allowlist management API (list_allowlist/add_exact/add_domain/add_wildcard
and friends), because og-society has no allowlist concept at all - it
accepts mail from any sender to a minted address, which is the point of the
feature it backs (arbitrary game/service signups, unknown senders in
advance). If a specific test suite genuinely needs to reject mail from an
unexpected sender, that filtering now belongs in the test code itself,
inspecting Email.derived_original_sender after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from mailflow.models import Email


@dataclass(frozen=True)
class MintedAddress:
    """An address minted via the og-society API, plus what's needed to poll it."""

    address: str
    alias_id: int


class MailflowClient:
    """Thin HTTP wrapper around a member's og-society vault.

    Parameters
    ----------
    base_url:
        Root URL of the og-society deployment, e.g. ``https://og-society.com``.
    api_token:
        A personal API token minted at ``/den/tokens`` on that account. The
        account needs enough daily-minting headroom for however many
        addresses a run creates - provisional (1/day) or operative (10/day)
        clearance will starve most CI runs; root is unlimited and is the
        realistic choice for a dedicated automation account.
    timeout:
        Default HTTP timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = 10.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Minting
    # ------------------------------------------------------------------

    def mint_address(
        self,
        *,
        game: str,
        domain: str = "mailinpot.com",
        local_part: str | None = None,
        notes: str = "",
        password: str = "n/a - minted by mailflow, not a real credential",
        reuse_existing: bool = True,
    ) -> MintedAddress:
        """Create a new vault entry on og-society and return its address.

        `domain` must be one the og-society deployment has configured in
        OGS_MAIL_DOMAINS. `game` is a required label in og-society's vault
        (it is shaped like a password manager, not a bare mailbox
        allocator) - pass something identifying the test run or suite.
        `password` exists for the same reason and is stored in the clear on
        the og-society side, same as every other vault entry - do not put a
        real credential here unless this run genuinely creates one and
        wants it remembered.

        Passing an explicit, deterministic `local_part` (rather than
        leaving it to be auto-generated) makes this idempotent by default:
        og-society rejects a duplicate address with 409, and
        `reuse_existing=True` (the default) catches exactly that and looks
        up the address it already minted instead of raising - handy so a
        test suite can mint once per test *case* rather than once per *run*
        without accumulating a fresh vault entry every time. Set
        `reuse_existing=False` to instead treat a collision as an error.
        """
        payload: dict[str, object] = {
            "game": game,
            "domain": domain,
            "password": password,
            "notes": notes,
        }
        if local_part:
            payload["local_part"] = local_part

        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.post(f"{self._base}/api/logins", json=payload)

        if resp.status_code == 409 and local_part and reuse_existing:
            wanted = f"{local_part}@{domain}".lower()
            for existing in self.list_addresses():
                if existing.address.lower() == wanted:
                    return existing
            # 409 said it exists, but not under this account - not ours to
            # reuse (someone else's, or a different account's earlier run).
            resp.raise_for_status()

        resp.raise_for_status()
        login = resp.json()["login"]
        return MintedAddress(address=login["email"], alias_id=login["id"])

    # ------------------------------------------------------------------
    # Reading mail
    # ------------------------------------------------------------------

    def check_for_email(self, minted: MintedAddress) -> Email | None:
        """One non-blocking check for the newest message addressed to
        `minted`, or None if nothing has arrived yet.

        Unlike the old Worker's `/api/wait/<recipient>`, there is no
        server-side long-poll here - og-society's API is a plain REST
        surface, not a push mechanism. mailflow.wait.wait_for_email supplies
        the polling loop this used to get from the server for free.
        """
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            list_resp = client.get(f"{self._base}/api/logins/{minted.alias_id}/messages")
        list_resp.raise_for_status()
        messages = list_resp.json()["messages"]
        if not messages:
            return None
        newest = messages[0]  # newest-first, per og-society's API

        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            content_resp = client.get(
                f"{self._base}/api/logins/{minted.alias_id}/messages/{newest['id']}/content"
            )
        content_resp.raise_for_status()
        content = content_resp.json()

        return Email.from_dict(
            {
                "received_at": newest["received_utc"],
                "recipient_address": minted.address,
                "derived_original_sender": newest["from"],
                "sender_match_basis": "from",
                "subject": newest["subject"],
                "body_text": content.get("text_body") or "",
                "html_body": content.get("html_body"),
                "message_id": newest.get("message_id"),
                "intermediary_sender": None,
            }
        )

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def list_addresses(self) -> list[MintedAddress]:
        """Every address this token's account has minted (not just this
        run's).

        There is deliberately no delete_address here: og-society only
        allows a token to mint and read, never to edit or delete an
        existing entry - the same rule applies to every account, including
        a dedicated QA one, so a leaked automation token cannot wipe a
        vault. Stale test addresses just accumulate; clean them up from
        /den/logins (cookie-authenticated) if that ever matters, or mint
        fewer of them (see mint_address's `local_part` - a deterministic
        local part per test case reuses the same address run over run
        instead of minting a fresh one every time).
        """
        with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/api/logins")
        resp.raise_for_status()
        return [
            MintedAddress(address=row["email"], alias_id=row["id"])
            for row in resp.json()["logins"]
        ]
