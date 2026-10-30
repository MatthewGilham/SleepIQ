import { expect, test } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { App, metricValue, sourceBanner } from "./App";
import type { DashboardData } from "./dashboardModel";
import { arrowDirection, nightFromSearch, searchForNight } from "./dashboardModel";

test("missing measurements remain missing, including legitimate zero values", () => {
  expect(metricValue(null)).toBe("Missing data");
  expect(metricValue("0")).toBe("0");
});
test("preview identifies synthetic data and disconnected operational status", () => {
  const html = renderToStaticMarkup(<App initial={{ kind: "preview" }} />);
  expect(html).toContain("Synthetic examples");
  expect(html).toContain("Not connected");
  expect(html).toContain("Missing data");
  expect(html).toContain("87.5");
  expect(html).toContain("Pilot ceiling");
  expect(html).toContain("Skip to content");
  expect(html).toContain("Mean SDNN");
  expect(html).not.toContain("Analyze");
});

const night = { wake_date: "2026-10-28", source: "Watch", onset_local: "2026-10-27T23:00", wake_local: "2026-10-28T07:00", start_offset_min: 0, end_offset_min: 0, session_s: 28800, asleep_s: 26400, core_s: 14400, deep_s: 3600, rem_s: 4200, awake_s: 1200, efficiency: 0.9565, flags: [], stages: [{ stage: "Core" as const, start_s: 0, duration_s: 14400 }, { stage: "Awake" as const, start_s: 14400, duration_s: 1200 }],
  physiology: [{ id: "hr", label: "Sleeping heart rate", value: 54, n: 6 }, { id: "hrv", label: "Overnight HRV", value: null, n: 0 }, { id: "temp", label: "Sleeping wrist temperature", value: 0, n: 1 }],
  score: { status: "insufficient_data" as const, overall: null, consistency: null, version: "pilot-1", ceiling: 92.5, missing: ["overnight_hrv", "consistency:insufficient_history"], components: { duration: { score: 100, weight: 30, neutral: false }, deep: { score: 75, weight: 10, neutral: true } }, consistency_detail: { available: false, reason: "insufficient_history", baseline_nights: 3 } } };
const data = { synthetic: true, versions: ["derive-1", "pilot-1"], import: { batches: 1, last_received_utc: 1793000000, nights: 3 }, latest: night, trend: { dates: ["2026-10-27", "2026-10-28"], asleep_h: [null, 7.33] } };
test("live dashboard shows an unscored night with reasons, gaps and genuine zero values", () => {
  const html = renderToStaticMarkup(<App initial={{ kind: "ready", data }} />);
  expect(html).toContain("Generated test data");
  expect(html).toContain("Insufficient");
  expect(html).toContain("overnight HRV, enough history for consistency");
  expect(html).toContain(`<span class="dur-part">7<span class="dur-unit">h</span></span> <span class="dur-part">20<span class="dur-unit">m</span></span>`);
  expect(html).toContain("23:00");
  expect(html).toContain("Missing data");
  expect(html).toContain("95.7");
  expect(html).toMatch(/metric-value">0 <small>°C/);
  expect(html).toContain("no recording");
  expect(html).toContain("pilot-neutral");
  expect(html).toContain("3 nights");
});
test("loading, error and empty live states are explicit and never show preview numbers", () => {
  const loading = renderToStaticMarkup(<App initial={{ kind: "loading" }} />);
  expect(loading).toContain("Loading your latest night");
  expect(loading).not.toContain("87.5");
  const failed = renderToStaticMarkup(<App initial={{ kind: "error", message: "Dashboard request failed (500)." }} />);
  expect(failed).toContain("could not load");
  expect(failed).toContain("Retry");
  expect(failed).not.toContain("87.5");
  const empty = renderToStaticMarkup(<App initial={{ kind: "ready", data: { ...data, latest: null, import: { batches: 0, last_received_utc: null, nights: 0 } } }} />);
  expect(empty).toContain("No sleep history available");
  expect(empty).toContain("No imports yet");
});

test("the viewed night round-trips through the address and ignores malformed values", () => {
  expect(nightFromSearch("?night=2026-10-27")).toBe("2026-10-27");
  expect(nightFromSearch("?night=abc")).toBeNull();
  expect(nightFromSearch("")).toBeNull();
  expect(searchForNight("2026-10-27")).toBe("?night=2026-10-27");
  expect(searchForNight(null)).toBe("");
});
test("arrow keys navigate only without modifiers and outside form fields", () => {
  const body = { tagName: "BODY" };
  expect(arrowDirection({ key: "ArrowLeft", target: body })).toBe(-1);
  expect(arrowDirection({ key: "ArrowRight", target: body })).toBe(1);
  expect(arrowDirection({ key: "ArrowLeft", target: { tagName: "INPUT" } })).toBe(0);
  expect(arrowDirection({ key: "ArrowRight", target: { tagName: "SELECT" } })).toBe(0);
  expect(arrowDirection({ key: "ArrowLeft", target: { tagName: "DIV", isContentEditable: true } })).toBe(0);
  expect(arrowDirection({ key: "ArrowLeft", target: body, altKey: true })).toBe(0);
  expect(arrowDirection({ key: "ArrowUp", target: body })).toBe(0);
});
test("the top strip names only a synthetic or design-preview source, and is absent for stored nights", () => {
  const ready = (synthetic: boolean) => ({ kind: "ready" as const, data: { synthetic } as DashboardData });
  expect(sourceBanner({ kind: "preview" })).toEqual(["Design preview", "Synthetic examples - no personal health data"]);
  expect(sourceBanner(ready(true))).toEqual(["Synthetic preview", "Generated test data - not your health records"]);
  expect(sourceBanner(ready(false))).toBeNull();
  expect(sourceBanner({ kind: "loading" })).toBeNull();
  expect(sourceBanner({ kind: "error", message: "x" })).toBeNull();
});
