/** Reject errors or unexpected responses before displaying a connected state. */
export async function checkHealth(signal: AbortSignal): Promise<void> {
  const response = await fetch("/api/v1/health", { signal });
  if (!response.ok) throw new Error("Unavailable");
  const body: unknown = await response.json();
  if (typeof body !== "object" || body === null || !("status" in body) || body.status !== "ok") {
    throw new Error("Unexpected response");
  }
}
