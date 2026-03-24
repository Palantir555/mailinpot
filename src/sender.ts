/**
 * Original-sender derivation logic.
 *
 * Priority order per the README:
 *  1. Parsed `From:` header, if it cleanly yields exactly one mailbox.
 *  2. Parsed `Sender:` header, if present and clean.
 *  3. Envelope sender as fallback.
 *
 * "Cleanly yields" means a single RFC-5322 mailbox address can be extracted
 * without heuristics.  The implementation keeps it simple: look for the last
 * angle-bracket address `<…>`, or take the bare address if no brackets exist.
 */

import type { SenderDerivation } from "./types.js";

/**
 * Extract the first bare e-mail address from a header value string.
 *
 * Handles the common forms:
 *   "Display Name <user@example.com>"
 *   "user@example.com"
 *   "<user@example.com>"
 */
export function extractAddress(header: string): string | null {
  if (!header || !header.trim()) return null;

  // Try angle-bracket form first.
  const bracketMatch = header.match(/<([^>@\s]+@[^>@\s]+)>/);
  if (bracketMatch) return bracketMatch[1]!.trim().toLowerCase();

  // Bare address form: must look like something@something.something
  const bareMatch = header.trim().match(/^([^\s@]+@[^\s@]+\.[^\s@]+)$/);
  if (bareMatch) return bareMatch[1]!.trim().toLowerCase();

  return null;
}

/**
 * Derive the original sender identity from email-message headers.
 *
 * @param fromHeader   Value of the `From:` header (may be undefined/empty).
 * @param senderHeader Value of the `Sender:` header (may be undefined/empty).
 * @param envelopeFrom Envelope MAIL FROM address (always available in the
 *                     Cloudflare Email Worker as `message.from`).
 */
export function deriveOriginalSender(
  fromHeader: string | undefined,
  senderHeader: string | undefined,
  envelopeFrom: string,
): SenderDerivation {
  if (fromHeader) {
    const addr = extractAddress(fromHeader);
    if (addr) return { address: addr, basis: "from" };
  }

  if (senderHeader) {
    const addr = extractAddress(senderHeader);
    if (addr) return { address: addr, basis: "sender" };
  }

  // Fall back to the envelope sender (already a bare address).
  return {
    address: envelopeFrom.trim().toLowerCase(),
    basis: "envelope",
  };
}
