import { afterEach, expect, test, vi } from "vitest";
import { checkHealth } from "./health";

afterEach(() => vi.unstubAllGlobals());

test("accepts the local service response and forwards cancellation", async () => {
  const request = vi.fn().mockResolvedValue(new Response('{"status":"ok"}'));
  vi.stubGlobal("fetch", request);
  const signal = new AbortController().signal;
  await checkHealth(signal);
  expect(request).toHaveBeenCalledWith("/api/v1/health", { signal });
});

test.each([null, {}, { status: "failed" }, "ok"])("rejects unexpected body %j", async body => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
  await expect(checkHealth(new AbortController().signal)).rejects.toThrow("Unexpected response");
});

test("rejects an HTTP error even if the body says ok", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"status":"ok"}', { status: 503 })));
  await expect(checkHealth(new AbortController().signal)).rejects.toThrow("Unavailable");
});

test("propagates a disconnected service", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network failure")));
  await expect(checkHealth(new AbortController().signal)).rejects.toThrow("Network failure");
});
