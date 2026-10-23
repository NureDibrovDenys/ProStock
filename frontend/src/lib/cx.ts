/** Склеює CSS-класи, пропускаючи порожні значення. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}
