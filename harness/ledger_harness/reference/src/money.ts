/** Money is an integer number of minor units (cents). */
export type Money = number;

export function money(dollars: number): Money {
  return Math.round(dollars * 100);
}

export function add(a: Money, b: Money): Money {
  return a + b;
}

export function sub(a: Money, b: Money): Money {
  return a - b;
}

export function mul(m: Money, factor: number): Money {
  return Math.round(m * factor);
}

export function format(m: Money): string {
  return "$" + (m / 100).toFixed(2);
}
