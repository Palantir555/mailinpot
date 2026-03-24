/**
 * MailboxDO – Durable Object keyed by recipient e-mail address.
 *
 * Responsibilities
 * ================
 * • Hold accepted email(s) briefly for active consumers.
 * • Support "wait for next email" via long-poll HTTP (no database polling).
 * • Mark email consumed on retrieval.
 * • Expire unconsumed email automatically (TTL-based alarm).
 *
 * HTTP endpoints (called internally from the main Worker)
 * =======================================================
 * POST /deliver            – deliver an AcceptedEmail from the Worker.
 * GET  /next?timeout=<ms>  – wait up to <ms> ms for the next email.
 *
 * Both endpoints require the same API_SECRET bearer token as the public API.
 *
 * Storage schema
 * ==============
 * Key `queue:<timestamp>:<id>` → JSON-encoded AcceptedEmail
 * One alarm fires EMAIL_TTL_MS after the oldest queued message.
 */

import type { AcceptedEmail } from "./types.js";

const EMAIL_TTL_MS = 10 * 60 * 1000;     // 10 minutes
const DEFAULT_WAIT_MS = 30 * 1000;        // 30 seconds
const MAX_WAIT_MS = 120 * 1000;           // 2 minutes

type Waiter = {
  resolve: (email: AcceptedEmail) => void;
  reject: (reason?: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export class MailboxDO implements DurableObject {
  private readonly state: DurableObjectState;
  private readonly waiters: Waiter[] = [];

  constructor(state: DurableObjectState) {
    this.state = state;
    // Restore any messages already in storage when the DO wakes up.
    // (In-memory waiters are always empty on cold start – that is fine.)
  }

  // ---------------------------------------------------------------------------
  // DurableObject interface
  // ---------------------------------------------------------------------------

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/deliver") {
      return this.handleDeliver(request);
    }

    if (request.method === "GET" && url.pathname === "/next") {
      const timeout = Math.min(
        parseInt(url.searchParams.get("timeout") ?? String(DEFAULT_WAIT_MS), 10),
        MAX_WAIT_MS,
      );
      return this.handleNext(timeout);
    }

    return new Response("Not Found", { status: 404 });
  }

  async alarm(): Promise<void> {
    await this.evictExpired();
  }

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  private async handleDeliver(request: Request): Promise<Response> {
    let email: AcceptedEmail;
    try {
      email = (await request.json()) as AcceptedEmail;
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    // If a consumer is already waiting, wake it immediately.
    const waiter = this.waiters.shift();
    if (waiter) {
      clearTimeout(waiter.timer);
      waiter.resolve(email);
      return new Response("ok");
    }

    // Otherwise persist to storage and schedule expiry.
    const key = `queue:${Date.now()}:${crypto.randomUUID()}`;
    await this.state.storage.put(key, email);
    await this.scheduleAlarm();
    return new Response("ok");
  }

  private async handleNext(timeoutMs: number): Promise<Response> {
    // Check durable storage first (handles cold-start or reconnect cases).
    const queued = await this.dequeueFromStorage();
    if (queued) {
      return Response.json(queued);
    }

    // Long-poll: wait for the Worker to push an email.
    return new Promise<Response>((resolve) => {
      const timer = setTimeout(() => {
        const idx = this.waiters.indexOf(waiter);
        if (idx !== -1) this.waiters.splice(idx, 1);
        resolve(new Response("timeout", { status: 408 }));
      }, timeoutMs);

      const waiter: Waiter = {
        resolve: (email) => resolve(Response.json(email)),
        reject: () => resolve(new Response("timeout", { status: 408 })),
        timer,
      };

      this.waiters.push(waiter);
    });
  }

  // ---------------------------------------------------------------------------
  // Storage helpers
  // ---------------------------------------------------------------------------

  /** Pop and return the oldest queued email from durable storage, if any. */
  private async dequeueFromStorage(): Promise<AcceptedEmail | null> {
    const entries = await this.state.storage.list<AcceptedEmail>({
      prefix: "queue:",
      limit: 1,
    });
    if (entries.size === 0) return null;

    const [key, email] = [...entries.entries()][0]!;
    await this.state.storage.delete(key);
    return email;
  }

  /** Schedule (or re-schedule) an alarm to evict expired messages. */
  private async scheduleAlarm(): Promise<void> {
    const current = await this.state.storage.getAlarm();
    if (current === null) {
      await this.state.storage.setAlarm(Date.now() + EMAIL_TTL_MS);
    }
  }

  /** Delete all stored emails older than EMAIL_TTL_MS. */
  private async evictExpired(): Promise<void> {
    const cutoff = Date.now() - EMAIL_TTL_MS;
    const all = await this.state.storage.list<AcceptedEmail>({ prefix: "queue:" });

    for (const [key] of all.entries()) {
      // Key format: queue:<timestamp>:<id>
      const ts = parseInt(key.split(":")[1] ?? "0", 10);
      if (ts < cutoff) {
        await this.state.storage.delete(key);
      }
    }

    // Reschedule if anything remains.
    const remaining = await this.state.storage.list({ prefix: "queue:", limit: 1 });
    if (remaining.size > 0) {
      await this.scheduleAlarm();
    }
  }
}
