export function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString("de-DE");
}

export function formatDuration(hours: number | null): string {
  if (hours === null || hours === undefined) return "\u2014";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `${h}h ${m}m`;
}
