import { afterEach, expect, test, vi } from "vitest";
import { backupLabel, loadBackupStatus } from "./backup";
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
test("header backup label never reports a failed or pending backup as healthy", () => {
  expect(backupLabel("Backup verified for 2026-10-28.")).toBe("Verified");
  expect(backupLabel("Backup storage is not configured.")).toBe("Not connected");
  expect(backupLabel("Backup failed. Check your backup folder and available disk space.")).toBe("Needs attention");
  expect(backupLabel("Backup verification is pending.")).toBe("Needs attention");
});
