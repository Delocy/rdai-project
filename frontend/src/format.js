// catalogue prices are invented and unit-less; shown in dollars to match how queries
// phrase budgets ("under 50")
export function money(value) {
  return `$${Number(value).toFixed(2)}`;
}
