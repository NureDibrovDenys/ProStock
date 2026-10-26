const numberFormat = new Intl.NumberFormat('uk-UA');
const timeFormat = new Intl.DateTimeFormat('uk-UA', { hour: '2-digit', minute: '2-digit' });

export const formatNumber = (value: number) => numberFormat.format(value);

export const formatTime = (iso: string) => timeFormat.format(new Date(iso));

export const formatSigned = (value: number) => (value > 0 ? `+${value}` : `${value}`);

/** "сьогодні о 09:42", "вчора о 18:10" або дата для старіших подій. */
export function formatRelativeDay(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

  if (sameDay(date, today)) return `сьогодні о ${formatTime(iso)}`;
  if (sameDay(date, yesterday)) return `вчора о ${formatTime(iso)}`;
  return new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }).format(date);
}

/** Час операції в стрічці: "09:42" для сьогоднішніх, "Вчора", далі — дата. */
export function formatOperationTime(iso: string): string {
  const date = new Date(iso);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === new Date().toDateString()) return formatTime(iso);
  if (date.toDateString() === yesterday.toDateString()) return 'Вчора';
  return new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'short' }).format(date);
}

/** Українська форма множини: plural(5, ['полиця', 'полиці', 'полиць']) → 'полиць'. */
export function plural(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}
