import { describe, expect, it } from "vitest";

import { formatEurCents } from "@/lib/money";

describe("formatEurCents", () => {
  it("renders eurocents as a EUR amount", () => {
    // 31_250 eurocents = €312.50 (the warehouse €500k @ 0.5‰ × 1.25 reference premium)
    expect(formatEurCents(31_250)).toContain("312.50");
    expect(formatEurCents(31_250)).toContain("€");
  });

  it("handles zero and large values", () => {
    expect(formatEurCents(0)).toContain("0.00");
    expect(formatEurCents(500_000_00)).toContain("500,000.00");
  });
});
