import { describe, it, expect } from "vitest";
import { extractAddress, deriveOriginalSender } from "../sender.js";

describe("extractAddress", () => {
  it("extracts from angle-bracket form with display name", () => {
    expect(extractAddress("Display Name <user@example.com>")).toBe("user@example.com");
  });

  it("extracts bare address", () => {
    expect(extractAddress("user@example.com")).toBe("user@example.com");
  });

  it("extracts from angle-bracket form without display name", () => {
    expect(extractAddress("<user@example.com>")).toBe("user@example.com");
  });

  it("normalises to lowercase", () => {
    expect(extractAddress("User@Example.COM")).toBe("user@example.com");
  });

  it("returns null for empty string", () => {
    expect(extractAddress("")).toBeNull();
  });

  it("returns null for non-email string", () => {
    expect(extractAddress("not an email")).toBeNull();
  });
});

describe("deriveOriginalSender", () => {
  it("uses From header when cleanly available", () => {
    const result = deriveOriginalSender(
      "Service <comms@myservice.com>",
      "forwarder@gmail.com",
      "bounce@gmail.com",
    );
    expect(result).toEqual({ address: "comms@myservice.com", basis: "from" });
  });

  it("falls back to Sender header when From is missing", () => {
    const result = deriveOriginalSender(
      undefined,
      "sender@myservice.com",
      "bounce@gmail.com",
    );
    expect(result).toEqual({ address: "sender@myservice.com", basis: "sender" });
  });

  it("falls back to envelope when From and Sender are missing", () => {
    const result = deriveOriginalSender(
      undefined,
      undefined,
      "envelope@myservice.com",
    );
    expect(result).toEqual({ address: "envelope@myservice.com", basis: "envelope" });
  });

  it("falls back to Sender header when From cannot be parsed", () => {
    const result = deriveOriginalSender(
      "not a valid address",
      "real@sender.com",
      "envelope@x.com",
    );
    expect(result).toEqual({ address: "real@sender.com", basis: "sender" });
  });

  it("falls back to envelope when neither From nor Sender can be parsed", () => {
    const result = deriveOriginalSender(
      "not valid",
      "also not valid",
      "envelope@x.com",
    );
    expect(result).toEqual({ address: "envelope@x.com", basis: "envelope" });
  });

  it("normalises envelope sender to lowercase", () => {
    const result = deriveOriginalSender(undefined, undefined, "User@Example.COM");
    expect(result.address).toBe("user@example.com");
  });
});
