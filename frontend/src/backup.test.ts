import { afterEach, expect, test, vi } from "vitest";
import { loadBackupStatus } from "./backup";
afterEach(() => vi.unstubAllGlobals());
test("shows the verified local date", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    backup: {status: "ok", last_success: "2026-10-29"}
  }))));
  expect(await loadBackupStatus(new AbortController().signal)).toBe("Backup verified for 2026-10-29.");
});
test("failure message never exposes internal error details", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
    backup: {status: "failed", error: "private-marker"}
  }))));
  const message = await loadBackupStatus(new AbortController().signal);
  expect(message).toContain("Backup failed");
  expect(message).not.toContain("private-marker");
});
test.each([null, {}, {backup: null}, {backup: {status: "ok", last_success: null}}])(
  "rejects incomplete status %j", async body => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    await expect(loadBackupStatus(new AbortController().signal)).rejects.toThrow();
  }
);
