import { describe, expect, it } from "vitest";
import { certificateLabel } from "./certificate";

const cert = (state: string, days: number | null) => ({ backup: {}, certificate: { state, days_left: days } });

describe("certificateLabel", () => {
  it("hides the item when the certificate is not configured", () => {
    expect(certificateLabel({ backup: {} })).toBeNull();
    expect(certificateLabel(null)).toBeNull();
  });
  it("describes each state with the day count", () => {
    expect(certificateLabel(cert("ok", 60))).toBe("60 days left");
    expect(certificateLabel(cert("due", 20))).toBe("Renewal due: 20 days left");
    expect(certificateLabel(cert("urgent", 3))).toBe("Renew now: 3 days left");
    expect(certificateLabel(cert("expired", -2))).toContain("Expired");
  });
  it("never reports an unreadable status as healthy", () => {
    expect(certificateLabel(cert("unknown", null))).toBe("Unknown");
    expect(certificateLabel({ certificate: { state: "something-new" } })).toBe("Unknown");
  });
});
