/**
 * KV-backed allowlist for the original-sender check.
 *
 * Key patterns stored in Workers KV:
 *   sender:exact:<address>   – exact e-mail address
 *   sender:domain:<domain>   – any address at that domain
 */

import type { Env } from "./types.js";

export const KV_PREFIX_EXACT = "sender:exact:";
export const KV_PREFIX_DOMAIN = "sender:domain:";

/**
 * Check whether `senderAddress` is on the allowlist.
 *
 * Checks exact address first, then domain.
 */
export async function isAllowed(
  senderAddress: string,
  kv: KVNamespace,
): Promise<boolean> {
  const addr = senderAddress.toLowerCase();
  const domain = addr.split("@")[1] ?? "";

  const exactKey = `${KV_PREFIX_EXACT}${addr}`;
  const domainKey = `${KV_PREFIX_DOMAIN}${domain}`;

  // Parallel KV reads for minimum latency.
  const [exactHit, domainHit] = await Promise.all([
    kv.get(exactKey),
    kv.get(domainKey),
  ]);

  return exactHit !== null || domainHit !== null;
}

/** Add an exact-address entry to the allowlist. */
export async function addExact(address: string, kv: KVNamespace): Promise<void> {
  await kv.put(`${KV_PREFIX_EXACT}${address.toLowerCase()}`, "1");
}

/** Remove an exact-address entry from the allowlist. */
export async function removeExact(address: string, kv: KVNamespace): Promise<void> {
  await kv.delete(`${KV_PREFIX_EXACT}${address.toLowerCase()}`);
}

/** Add a domain entry to the allowlist. */
export async function addDomain(domain: string, kv: KVNamespace): Promise<void> {
  await kv.put(`${KV_PREFIX_DOMAIN}${domain.toLowerCase()}`, "1");
}

/** Remove a domain entry from the allowlist. */
export async function removeDomain(domain: string, kv: KVNamespace): Promise<void> {
  await kv.delete(`${KV_PREFIX_DOMAIN}${domain.toLowerCase()}`);
}

/** List all allowlist entries (keys only, no values). */
export async function listEntries(kv: KVNamespace): Promise<string[]> {
  const results: string[] = [];
  let cursor: string | undefined;

  do {
    const page: KVNamespaceListResult<unknown, string> = await kv.list({
      prefix: "sender:",
      cursor,
    });
    for (const key of page.keys) {
      results.push(key.name);
    }
    cursor = page.list_complete ? undefined : (page as { cursor?: string }).cursor;
  } while (cursor);

  return results;
}

/** Require a valid API secret on HTTP management requests. */
export function requireAuth(request: Request, env: Env): Response | null {
  const auth = request.headers.get("Authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  if (token !== env.API_SECRET) {
    return new Response("Unauthorized", { status: 401 });
  }
  return null;
}
