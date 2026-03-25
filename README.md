# qa-mail-ingest

A small, app-agnostic inbound email ingestion system for automated testing.

This project is meant to receive real emails sent to unique test-run addresses, filter them by an allowlist of expected original senders, and make the accepted emails available to Python test code without wasteful database polling.

The design prioritizes:

- simplicity
- low cost
- staying within Cloudflare free-tier limits where practical
- deterministic behavior for parallel test runs
- clean separation between infrastructure code and app-specific email parsing

---

## Final architecture

### Overview

1. Cloudflare Email Routing receives inbound email for a catch-all QA domain.
2. A Cloudflare Email Worker processes each incoming email.
3. The Worker derives the **original sender** identity and checks it against an allowlist.
4. If the email is accepted:
   - it is delivered to a **Durable Object** keyed by recipient address
   - it is also stored briefly as a fallback/debug record with short retention
5. Python code retrieves the email through a small app-agnostic client library.
6. App-specific code parses the subject/body for links, OTP codes, etc.

### Why this design

- **Recipient address is the primary routing key**, which makes parallel runs safe and deterministic.
- **Durable Objects handle live delivery**, so consumers do not need to poll a database.
- **KV stores the allowlist**, which is a good fit for a read-heavy, rarely modified dataset.
- **Short-lived fallback storage exists only for resilience and basic debugging**, not as the primary transport.

This keeps the hot path simple and avoids turning the database into a mailbox that gets hammered by polling.

---

## Core design decisions

### Recipient-based correlation

Each test run uses a unique email address such as:

`run-abc123@qa.example.com`

That address is the only key used to retrieve the message.

This avoids ambiguity and cross-talk between concurrent runs.

### Sender-based allowlist

Filtering is based on the **derived original sender**, not on the recipient.

The allowlist supports two entry types:

- exact sender address, such as `comms@myservice.com`
- sender domain, such as `myservice.com`

The intermediary forwarder is not part of the correctness path.

Example:

- original sender: `comms@myservice.com`
- forwarder: `devForwarder@gmail.com`
- final recipient: `testrun@qa.example.com`

In that case:

- retrieval uses `testrun@qa.example.com`
- allowlist uses `comms@myservice.com`
- `devForwarder@gmail.com` is optional debug metadata only

### Original-sender derivation rule

The system will derive a single sender identity for allowlist checks using this order:

1. parsed `From:` address, if it cleanly yields one mailbox
2. parsed `Sender:` address, if present and clean
3. envelope sender, as fallback

The system will also record which rule was used, so allowlist decisions remain explainable without storing excessive debug data.

### Avoid database polling

Consumers should not poll D1 or any other database waiting for mail.

Instead:

- the Worker pushes accepted mail into a Durable Object keyed by recipient address
- Python waits on a small HTTP API backed by that Durable Object
- short-lived storage is only a fallback/debug utility

This is the main free-tier optimization.

---

## Cloudflare components

### 1. Email Routing

Use Cloudflare Email Routing in catch-all mode on a dedicated QA mail domain or subdomain.

Purpose:

- receive real inbound email
- avoid running our own SMTP server
- allow arbitrary per-run recipient addresses

### 2. Email Worker

The Worker is responsible for:

- reading envelope sender and recipient
- parsing sender-related headers
- deriving the original sender
- checking the allowlist
- dropping unwanted mail immediately
- passing accepted mail to the live coordination layer
- optionally writing a short-lived fallback/debug record

The Worker should remain lightweight.

### 3. Workers KV

KV stores the allowlist.

Key patterns:

- `sender:exact:comms@myservice.com`
- `sender:domain:myservice.com`

The allowlist CLI will manage these keys.

### 4. Durable Objects

Durable Objects are the primary live-delivery mechanism.

One Durable Object instance will be keyed by recipient address.

Responsibilities:

- hold accepted mail briefly for active consumers
- support “wait for next email” behavior
- return the next available accepted email for a recipient
- mark email consumed
- expire old state automatically

This is the core coordination mechanism.

### 5. Short-lived fallback storage

A short-lived fallback/debug store will exist, but it is not the hot path.

Use it only for:

- brief resilience if a consumer is not actively waiting
- basic debugging
- temporary inspection during development

Retention should be aggressively short.

This can be implemented with D1 if needed, but only after the live path is working.

---

## Minimal stored data

Do not store more than needed.

For each accepted email, store only:

- `received_at`
- `recipient_address`
- `derived_original_sender`
- `sender_match_basis`
- `subject`
- `body_text`
- `message_id` if present
- `intermediary_sender` only if it can be extracted cleanly and cheaply

Do **not** store raw MIME long-term by default.

Do **not** keep large header dumps unless later debugging proves they are necessary.

---

## Python-side API

Create an app-agnostic Python package named `mailflow`.

Its job is to hide the infrastructure details and expose a clean interface to application code.

### Responsibilities

- generate or reserve a unique recipient address for a test run
- wait for an email for that address
- return a normalized email object
- expose simple text/body accessors
- let app-specific code parse OTPs, links, etc.

### Proposed package structure

- `mailflow.client` — HTTP client for the Cloudflare-backed service
- `mailflow.models` — typed email objects
- `mailflow.wait` — blocking wait helpers and timeouts
- `mailflow.addressing` — recipient address generation helpers

Do **not** put application-specific parsing in `mailflow`.

That belongs in the consuming app.

### Intended usage

A consumer should be able to do something like:

1. generate a unique recipient address
2. use that address in the app under test
3. wait for the accepted email
4. pass the returned message object to app-specific parsing code

---

## Manual setup required before coding

These are human tasks that should be completed before asking an AI to write infrastructure code.

### Cloudflare and domain setup

- [x] Create a Cloudflare account
- [x] Buy or assign a dedicated QA mail domain or subdomain : mailinpot.com
- [x] Move DNS authority for that domain to Cloudflare
- [x] Enable Email Routing for that domain
- [x] Configure the catch-all inbound route
- [x] Create API tokens for deployment and CLI usage

### Local development setup

- [x] Install Node and Wrangler for Worker deployment
- [x] Install Python toolchain for the client library and CLI
- [x] Create a new GitHub repo for this project

---

---

## Deployment

> **Prerequisites:** complete all steps in [Manual setup required before
> coding](#manual-setup-required-before-coding) first.

### 1. Deploy the Cloudflare Worker

```bash
cd /path/to/mailinpot

# 1a. Create the KV namespace for the allowlist (one-time setup)
npx wrangler kv:namespace create ALLOWLIST_KV
npx wrangler kv:namespace create ALLOWLIST_KV --preview

# 1b. Edit wrangler.toml and paste in the two IDs printed above:
#     Replace  id         = "REPLACE_WITH_KV_ID"
#     Replace  preview_id = "REPLACE_WITH_KV_PREVIEW_ID"

# 1c. Set the API bearer secret (stored encrypted in Cloudflare, never committed)
npx wrangler secret put API_SECRET

# 1d. Deploy
npx wrangler deploy
```

The command prints the Worker URL, e.g.
`https://mailinpot.<account>.workers.dev`.  Note it — you need it as
`MAILINPOT_URL` below.

### 2. Configure Cloudflare Email Routing

In the Cloudflare dashboard:

1. Go to **Email → Email Routing** for your QA domain (`mailinpot.com`).
2. Under the catch-all rule, choose **Send to a Worker**.
3. Select the `mailinpot` Worker you just deployed.
4. Save.

All inbound mail for `*@mailinpot.com` now flows into the Worker.

### 3. Install the Python package and CLI

```bash
# From the repo root (editable install so you get the latest code)
pip install -e mailflow/

# or with uv:
uv pip install -e mailflow/
```

### 4. Set environment variables

```bash
export MAILINPOT_URL=https://mailinpot.<account>.workers.dev
export MAILINPOT_SECRET=<the secret you chose in step 1c>
```

Add these to your shell profile or `.env` file for convenience.

### 5. Populate the sender allowlist

Emails are silently dropped unless the original sender is on the allowlist.
Add entries before running tests:

```bash
# Allow all mail from a domain
mailinpot-allowlist add domain myservice.com

# Or allow a single sender address only
mailinpot-allowlist add exact noreply@myservice.com

# Inspect the current list
mailinpot-allowlist list

# Remove an entry
mailinpot-allowlist remove domain myservice.com
```

---

## Quick start

### Wait for a specific address

```bash
python -m mailflow run-test123@mailinpot.com
```

Blocks until an email arrives (60 s default timeout), then prints all
metadata and the raw message body to stdout.

### Auto-generate a fresh address

```bash
python -m mailflow
```

A unique address (e.g. `run-4a7f1c9b2e30@mailinpot.com`) is printed to
stdout first so you can copy it to the app under test.  Use `--prefix` to
give it a meaningful label:

```bash
python -m mailflow --prefix password-reset --timeout 120
```

### Use `mailflow` from Python test code

```python
from mailflow.addressing import generate_recipient
from mailflow.client import MailflowClient
from mailflow.wait import wait_for_email

client = MailflowClient(
    base_url="https://mailinpot.<account>.workers.dev",
    api_secret="<secret>",
)

# Pick a unique address for this test run
recipient = generate_recipient(prefix="password-reset")

# … trigger the email in your app under test …

# Wait for it (raises EmailTimeoutError if nothing arrives within 60 s)
email = wait_for_email(client, recipient, timeout=60)

# Hand off to your app-specific parsing code
assert "Reset your password" in email.subject
otp = my_app.extract_otp(email.body_text)
```


## Implementation plan

### Phase 1 — repo bootstrap

- [x] Create repo structure
- [x] Add this README
- [x] Add license
- [x] Add `.gitignore`
- [x] Decide package/module names and directory layout

### Phase 2 — addressing and message model

- [x] Define recipient address format for unique runs
- [x] Define normalized accepted-email model
- [x] Define minimal stored fields
- [x] Define retention policy

### Phase 3 — allowlist subsystem

- [x] Implement KV-backed allowlist lookups
- [x] Implement exact-address matching
- [x] Implement domain matching
- [x] Implement allowlist CLI for add/remove/list operations

### Phase 4 — Worker ingestion path

- [x] Implement Email Worker entrypoint
- [x] Parse sender-related headers
- [x] Derive original sender using the chosen rule
- [x] Check allowlist
- [x] Drop rejected mail
- [x] Route accepted mail to the Durable Object for the recipient

### Phase 5 — live coordination layer

- [x] Implement Durable Object keyed by recipient address
- [x] Implement “wait for next email” behavior
- [x] Implement consume/delete behavior
- [x] Implement expiry and cleanup

### Phase 6 — fallback/debug storage

- [x] Add short-lived fallback storage
- [x] Store only minimal fields
- [x] Add short retention cleanup
- [x] Keep this off the hot path

### Phase 7 — Python client library

- [x] Implement `mailflow` package
- [x] Implement recipient address generation helper
- [x] Implement blocking wait API
- [x] Implement normalized email model
- [x] Add basic convenience accessors for subject/text/body

### Phase 8 — testing

- [x] Unit test sender derivation
- [x] Unit test allowlist matching
- [x] Unit test recipient-based routing
- [ ] Integration test with real inbound email
- [ ] Integration test with forwarded email
- [ ] Integration test with parallel runs

### Phase 9 — operational hardening

- [ ] Add structured logging
- [ ] Add minimal metrics/counters
- [ ] Add retention enforcement
- [ ] Document free-tier assumptions and limitations

---

## Non-goals

This project is **not** intended to become:

- a general-purpose mailbox service
- a long-term email archive
- a rich email search product
- a full forensic/debug email preservation system
- a high-volume production mail pipeline

---

## Handoff notes for coding AI

When implementing, follow these constraints:

1. Keep the hot path simple.
2. Do not introduce database polling.
3. Use recipient address as the only retrieval key.
4. Use derived original sender for allowlist checks.
5. Treat intermediary forwarders as optional metadata only.
6. Keep stored data minimal.
7. Prefer short retention and delete-on-consume behavior.
8. Keep the Python package app-agnostic.
9. Optimize for clarity and correctness before cleverness.
10. Stay within Cloudflare free-tier limits where practical, but do not overcomplicate the system just to save tiny amounts of usage.

---

## Current recommended v1 scope

Build v1 with:

- Cloudflare Email Routing catch-all
- Email Worker
- KV allowlist
- Durable Objects for live delivery
- minimal short-lived fallback storage
- `mailflow` Python client package
- allowlist management CLI

That is the cleanest balance of simplicity, cost control, and engineering quality for the current requirements.
