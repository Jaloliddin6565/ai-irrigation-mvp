/** Formatting helpers shared across pages. All dates from the backend are
 * ISO strings (date or datetime) in Asia/Tashkent-anchored calculations —
 * we only format them for display here, never re-derive them. */

const dateFormatter = new Intl.DateTimeFormat("uz-UZ", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const dateTimeFormatter = new Intl.DateTimeFormat("uz-UZ", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return dateFormatter.format(parsed);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return dateTimeFormatter.format(parsed);
}

export function formatNumber(value: number | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("uz-UZ", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function formatMm(value: number | null | undefined): string {
  return `${formatNumber(value)} mm`;
}

export function formatM3(value: number | null | undefined): string {
  return `${formatNumber(value, 0)} m³`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${formatNumber(value * 100, 0)}%`;
}

export function formatHectares(value: number | null | undefined): string {
  return `${formatNumber(value, 2)} ga`;
}

export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}
