// prices are invented and unit-less, shown in dollars because budgets are typed that way
export function money(value) {
  return `$${Number(value).toFixed(2)}`;
}
