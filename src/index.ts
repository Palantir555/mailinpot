/**
 * Cloudflare Worker entrypoint for mailinpot.
 *
 * Handles two types of events:
 *
 * 1. Email events  – Cloudflare Email Routing delivers inbound emails here.
 *    Flow: derive sender → check allowlist → route to MailboxDO.
 *
 * 2. HTTP fetch    – Serves the management + consumer REST API.
 *
 * REST API
 * ========
 * All endpoints require `Authorization: Bearer <API_SECRET>` unless noted.
 *
 * Consumer:
 *   GET /api/wait/<recipient>?timeout=<ms>
 *     Long-poll: returns the next email for <recipient> or 408 on timeout.
 *
 * Allowlist management:
 *   GET    /api/allowlist              – list all entries
 *   PUT    /api/allowlist/exact/<addr> – add exact-address entry
 *   DELETE /api/allowlist/exact/<addr> – remove exact-address entry
 *   PUT    /api/allowlist/domain/<dom> – add domain entry
 *   DELETE /api/allowlist/domain/<dom> – remove domain entry
 */

import { deriveOriginalSender } from "./sender.js";
import { isAllowed, addExact, removeExact, addDomain, removeDomain, listEntries, requireAuth } from "./allowlist.js";
import { MailboxDO } from "./mailbox.js";
import type { AcceptedEmail, Env } from "./types.js";

export { MailboxDO };

export default {
  // -------------------------------------------------------------------------
  // Email handler – triggered by Cloudflare Email Routing
  // -------------------------------------------------------------------------
  async email(message: ForwardableEmailMessage, env: Env): Promise<void> {
    const fromHeader = message.headers.get("From") ?? undefined;
    const senderHeader = message.headers.get("Sender") ?? undefined;
    const envelopeFrom = message.from;

    const derived = deriveOriginalSender(fromHeader, senderHeader, envelopeFrom);

    const allowed = await isAllowed(derived.address, env.ALLOWLIST_KV);
    if (!allowed) {
      // Drop silently – do not forward.
      message.setReject("Message rejected by allowlist");
      return;
    }

    // Extract plain-text body from the raw message stream.
    // Use a simple passthrough reader; for v1 we capture as-is.
    const bodyText = await readBodyText(message);

    const email: AcceptedEmail = {
      receivedAt: new Date().toISOString(),
      recipientAddress: message.to.toLowerCase(),
      derivedOriginalSender: derived.address,
      senderMatchBasis: derived.basis,
      subject: message.headers.get("Subject") ?? "",
      bodyText,
      messageId: message.headers.get("Message-ID") ?? undefined,
    };

    // Deliver to the MailboxDO for the recipient.
    const mailboxId = env.MAILBOX.idFromName(email.recipientAddress);
    const mailboxStub = env.MAILBOX.get(mailboxId);
    await mailboxStub.fetch(
      new Request("https://do/deliver", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(email),
      }),
    );
  },

  // -------------------------------------------------------------------------
  // HTTP handler – management API and consumer long-poll
  // -------------------------------------------------------------------------
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const { method, pathname } = { method: request.method, pathname: url.pathname };

    // All API routes require authentication.
    const authError = requireAuth(request, env);
    if (authError) return authError;

    // ----- Consumer: wait for next email -----
    const waitMatch = pathname.match(/^\/api\/wait\/(.+)$/);
    if (method === "GET" && waitMatch) {
      const recipient = decodeURIComponent(waitMatch[1]!).toLowerCase();
      const timeout = url.searchParams.get("timeout") ?? undefined;
      const doId = env.MAILBOX.idFromName(recipient);
      const stub = env.MAILBOX.get(doId);
      const doUrl = new URL("https://do/next");
      if (timeout) doUrl.searchParams.set("timeout", timeout);
      return stub.fetch(new Request(doUrl.toString()));
    }

    // ----- Allowlist management -----
    if (method === "GET" && pathname === "/api/allowlist") {
      const entries = await listEntries(env.ALLOWLIST_KV);
      return Response.json({ entries });
    }

    const exactMatch = pathname.match(/^\/api\/allowlist\/exact\/(.+)$/);
    if (exactMatch) {
      const addr = decodeURIComponent(exactMatch[1]!);
      if (method === "PUT") {
        await addExact(addr, env.ALLOWLIST_KV);
        return new Response("ok");
      }
      if (method === "DELETE") {
        await removeExact(addr, env.ALLOWLIST_KV);
        return new Response("ok");
      }
    }

    const domainMatch = pathname.match(/^\/api\/allowlist\/domain\/(.+)$/);
    if (domainMatch) {
      const domain = decodeURIComponent(domainMatch[1]!);
      if (method === "PUT") {
        await addDomain(domain, env.ALLOWLIST_KV);
        return new Response("ok");
      }
      if (method === "DELETE") {
        await removeDomain(domain, env.ALLOWLIST_KV);
        return new Response("ok");
      }
    }

    return new Response("Not Found", { status: 404 });
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Read the text body of an inbound email message.
 *
 * The Cloudflare EmailMessage exposes the raw RFC-5322 stream via `.raw`.
 * For v1 we collect all bytes and attempt UTF-8 decode; proper MIME parsing
 * (multipart, base64 parts) can be added in a later phase.
 */
async function readBodyText(message: ForwardableEmailMessage): Promise<string> {
  try {
    const reader = message.raw.getReader();
    const chunks: Uint8Array[] = [];
    let done = false;
    while (!done) {
      const result = await reader.read();
      done = result.done;
      if (result.value) chunks.push(result.value);
    }
    const full = new Uint8Array(chunks.reduce((acc, c) => acc + c.length, 0));
    let offset = 0;
    for (const chunk of chunks) {
      full.set(chunk, offset);
      offset += chunk.length;
    }
    return new TextDecoder().decode(full);
  } catch {
    return "";
  }
}
