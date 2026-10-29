export async function loadBackupStatus(signal: AbortSignal): Promise<string> {
  const response = await fetch("/api/v1/status", { signal });
  if (!response.ok) throw new Error("Status unavailable");
  const body: unknown = await response.json();
  if (typeof body !== "object" || body === null || !("backup" in body)) {
    throw new Error("Unexpected status");
  }
  const backup = body.backup;
  if (typeof backup !== "object" || backup === null || !("status" in backup)) {
    throw new Error("Unexpected status");
  }
  if (backup.status === "failed") return "Backup failed. Check your backup folder and available disk space.";
  if (backup.status === "pending") return "Backup verification is pending.";
  if (backup.status === "not_configured") return "Backup storage is not configured.";
  if (backup.status === "ok" && "last_success" in backup && typeof backup.last_success === "string"
      && /^\d{4}-\d{2}-\d{2}$/.test(backup.last_success)) {
    return `Backup verified for ${backup.last_success}.`;
  }
  throw new Error("Unexpected status");
}
/** Short header label for the longer owner-facing status message. */
export function backupLabel(message: string): string {
  if (message.startsWith("Backup verified")) return "Verified";
  if (message.includes("not configured")) return "Not connected";
  return "Needs attention";
}
