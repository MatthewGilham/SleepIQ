/** Header label for the sync certificate, or null when the launcher did not configure it. */
export function certificateLabel(body: unknown): string | null {
  if (typeof body !== "object" || body === null || !("certificate" in body)) return null;
  const cert = body.certificate;
  if (typeof cert !== "object" || cert === null || !("state" in cert)) return null;
  const days = "days_left" in cert && typeof cert.days_left === "number" ? cert.days_left : null;
  switch (cert.state) {
    case "ok": return days === null ? "OK" : `${days} days left`;
    case "due": return `Renewal due: ${days} days left`;
    case "urgent": return `Renew now: ${days} days left`;
    case "expired": return "Expired: uploads will fail";
    default: return "Unknown";
  }
}

export async function loadCertificateLabel(signal: AbortSignal): Promise<string | null> {
  const response = await fetch("/api/v1/status", { signal });
  if (!response.ok) return null;
  return certificateLabel(await response.json());
}
