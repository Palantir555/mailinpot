import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  isAllowed,
  addExact,
  removeExact,
  addDomain,
  removeDomain,
  addWildcard,
  removeWildcard,
  KV_PREFIX_EXACT,
  KV_PREFIX_DOMAIN,
  KV_PREFIX_WILDCARD,
} from "../allowlist.js";

/** Minimal in-memory KV mock. */
function makeKV(): KVNamespace {
  const store = new Map<string, string>();
  return {
    get: async (key: string) => store.get(key) ?? null,
    put: async (key: string, value: string) => { store.set(key, value); },
    delete: async (key: string) => { store.delete(key); },
    list: async ({ prefix = "", cursor }: { prefix?: string; cursor?: string } = {}) => {
      const keys = [...store.keys()]
        .filter((k) => k.startsWith(prefix))
        .map((name) => ({ name }));
      return { keys, list_complete: true, cursor: undefined };
    },
    getWithMetadata: async () => ({ value: null, metadata: null }),
  } as unknown as KVNamespace;
}

describe("allowlist", () => {
  let kv: KVNamespace;

  beforeEach(() => {
    kv = makeKV();
  });

  it("rejects a sender not on the allowlist", async () => {
    expect(await isAllowed("user@example.com", kv)).toBe(false);
  });

  it("accepts a sender added by exact address", async () => {
    await addExact("user@example.com", kv);
    expect(await isAllowed("user@example.com", kv)).toBe(true);
  });

  it("accepts a sender whose domain is on the allowlist", async () => {
    await addDomain("example.com", kv);
    expect(await isAllowed("user@example.com", kv)).toBe(true);
    expect(await isAllowed("other@example.com", kv)).toBe(true);
  });

  it("does not accept a sender from a different domain", async () => {
    await addDomain("example.com", kv);
    expect(await isAllowed("user@other.com", kv)).toBe(false);
  });

  it("removeExact removes the exact entry", async () => {
    await addExact("user@example.com", kv);
    await removeExact("user@example.com", kv);
    expect(await isAllowed("user@example.com", kv)).toBe(false);
  });

  it("removeDomain removes the domain entry", async () => {
    await addDomain("example.com", kv);
    await removeDomain("example.com", kv);
    expect(await isAllowed("user@example.com", kv)).toBe(false);
  });

  it("stores exact keys with correct prefix", async () => {
    await addExact("user@example.com", kv);
    const list = await kv.list({ prefix: KV_PREFIX_EXACT });
    expect(list.keys.map((k) => k.name)).toContain(
      `${KV_PREFIX_EXACT}user@example.com`,
    );
  });

  it("stores domain keys with correct prefix", async () => {
    await addDomain("example.com", kv);
    const list = await kv.list({ prefix: KV_PREFIX_DOMAIN });
    expect(list.keys.map((k) => k.name)).toContain(
      `${KV_PREFIX_DOMAIN}example.com`,
    );
  });

  it("is case-insensitive for addresses", async () => {
    await addExact("User@Example.COM", kv);
    expect(await isAllowed("user@example.com", kv)).toBe(true);
  });

  it("accepts any sender when the global wildcard is set", async () => {
    await addWildcard(kv);
    expect(await isAllowed("anyone@example.com", kv)).toBe(true);
    expect(await isAllowed("other@totally-different.org", kv)).toBe(true);
  });

  it("rejects senders after the global wildcard is removed", async () => {
    await addWildcard(kv);
    await removeWildcard(kv);
    expect(await isAllowed("anyone@example.com", kv)).toBe(false);
  });

  it("stores wildcard key with correct prefix", async () => {
    await addWildcard(kv);
    const list = await kv.list({ prefix: KV_PREFIX_WILDCARD });
    expect(list.keys.map((k) => k.name)).toContain(`${KV_PREFIX_WILDCARD}*`);
  });
});
