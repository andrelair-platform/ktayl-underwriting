// Money on this platform is stored as eurocents (minor units, integer). Format for display only —
// never do arithmetic on the formatted string.

const EUR = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });

export function formatEurCents(minor: number): string {
  return EUR.format(minor / 100);
}
