import { describe, it, expect } from "vitest";
import { sortItems } from "./sort";

interface TestItem {
  name: string;
  value: number;
}

describe("sortItems", () => {
  const items: TestItem[] = [
    { name: "C", value: 3 },
    { name: "A", value: 1 },
    { name: "B", value: 2 },
  ];

  it("sorts strings ascending", () => {
    const result = sortItems(items, "name", "asc");
    expect(result.map((i) => i.name)).toEqual(["A", "B", "C"]);
  });

  it("sorts strings descending", () => {
    const result = sortItems(items, "name", "desc");
    expect(result.map((i) => i.name)).toEqual(["C", "B", "A"]);
  });

  it("sorts numbers ascending", () => {
    const result = sortItems(items, "value", "asc");
    expect(result.map((i) => i.value)).toEqual([1, 2, 3]);
  });

  it("does not mutate original array", () => {
    const original = [...items];
    sortItems(items, "name", "asc");
    expect(items).toEqual(original);
  });

  it("handles null values", () => {
    const mixed = [
      { name: "A", value: 1 },
      { name: null as any, value: 2 },
      { name: "B", value: 3 },
    ];
    const result = sortItems(mixed, "name", "asc");
    expect(result[result.length - 1].name).toBeNull();
  });
});
