/**
 * Shared types used across the Worker and the MailboxDO Durable Object.
 *
 * Keep this file free of runtime logic so it can be imported by both
 * `src/index.ts` (Worker) and `src/mailbox.ts` (Durable Object) without
 * creating circular dependencies.
 */

/**
 * The minimal representation of an accepted email that is stored in the
 * Durable Object and returned to Python consumers.
 *
 * Field names are camelCase because they cross the wire as JSON and are
 * mapped to snake_case by `mailflow.models.Email.from_dict()` on the Python
 * side.  Do not rename fields here without updating that mapping.
 */
export interface AcceptedEmail {
  /** ISO-8601 timestamp recorded at the moment the Worker accepted the message. */
  receivedAt: string;

  /** The unique test-run address the message was addressed to (lowercased).
   *  This is the primary retrieval key – see README §Recipient-based correlation. */
  recipientAddress: string;

  /** The derived original sender address used for the allowlist check (lowercased).
   *  Never the forwarding intermediary.  See README §Original-sender derivation rule. */
  derivedOriginalSender: string;

  /** Which header rule produced `derivedOriginalSender`:
   *    "from"     – parsed From: header
   *    "sender"   – parsed Sender: header (From: was absent or unparseable)
   *    "envelope" – MAIL FROM envelope address (last-resort fallback) */
  senderMatchBasis: "from" | "sender" | "envelope";

  /** Decoded Subject: header value, or empty string if absent. */
  subject: string;

  /** Raw message body as decoded UTF-8 text.
   *  In v1 this is the full RFC-5322 stream; proper MIME unwrapping is a
   *  future-phase concern. */
  bodyText: string;

  /** RFC-5322 Message-ID header value, if present. */
  messageId?: string;

  /** The forwarding intermediary address, if it could be extracted cheaply.
   *  Stored for debug purposes only; never used for routing or filtering. */
  intermediarySender?: string;
}

/**
 * Intermediate result produced by `deriveOriginalSender()` in `sender.ts`.
 * Carries both the resolved address and a record of which rule was applied,
 * so the allowlist decision remains explainable.
 */
export interface SenderDerivation {
  /** The derived sender address (lowercased). */
  address: string;
  /** The header rule that produced `address`. */
  basis: "from" | "sender" | "envelope";
}

/**
 * Cloudflare Worker environment bindings.
 *
 * Declared in `wrangler.toml`; Cloudflare injects the concrete objects at
 * runtime.  For local `wrangler dev` runs, preview IDs / `.dev.vars` are used.
 */
export interface Env {
  /** Workers KV namespace holding the sender allowlist.
   *  Keys: `sender:exact:<addr>` and `sender:domain:<domain>`. */
  ALLOWLIST_KV: KVNamespace;

  /** Durable Object namespace for per-recipient mailboxes (MailboxDO). */
  MAILBOX: DurableObjectNamespace;

  /** Shared secret required on all HTTP API requests as `Bearer <API_SECRET>`.
   *  Set via `wrangler secret put API_SECRET` in production. */
  API_SECRET: string;
}
