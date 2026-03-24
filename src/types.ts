/** Shared types used across the Worker and Durable Object. */

/** A normalized accepted email stored and delivered by the system. */
export interface AcceptedEmail {
  receivedAt: string;       // ISO-8601
  recipientAddress: string;
  derivedOriginalSender: string;
  senderMatchBasis: "from" | "sender" | "envelope";
  subject: string;
  bodyText: string;
  messageId?: string;
  intermediarySender?: string;
}

/** Result of deriving the original sender from message headers. */
export interface SenderDerivation {
  address: string;
  basis: "from" | "sender" | "envelope";
}

/** Bindings available in the Worker environment. */
export interface Env {
  ALLOWLIST_KV: KVNamespace;
  MAILBOX: DurableObjectNamespace;
  API_SECRET: string;
}
