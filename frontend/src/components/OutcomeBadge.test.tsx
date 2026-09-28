import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OutcomeBadge } from "@/components/OutcomeBadge";

describe("OutcomeBadge", () => {
  it("labels each appetite outcome", () => {
    render(<OutcomeBadge outcome="refer" />);
    expect(screen.getByText("Refer")).toBeDefined();
  });

  it("renders the bound and unassessed states", () => {
    const { rerender } = render(<OutcomeBadge outcome="bound" />);
    expect(screen.getByText("Bound")).toBeDefined();
    rerender(<OutcomeBadge outcome="unassessed" />);
    expect(screen.getByText("Unassessed")).toBeDefined();
  });
});
