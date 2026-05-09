export function sortItems<T extends Record<string, any>>(
  items: T[],
  column: string,
  direction: "asc" | "desc"
): T[] {
  return [...items].sort((a, b) => {
    const va = a[column];
    const vb = b[column];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const multiplier = direction === "desc" ? -1 : 1;
    if (typeof va === "string" && typeof vb === "string") {
      return multiplier * va.localeCompare(vb);
    }
    return multiplier * ((va as number) - (vb as number));
  });
}
