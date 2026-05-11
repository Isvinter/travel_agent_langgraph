import { describe, it, expect } from "vitest";
import { formatDate, formatDuration } from "./format";

describe("formatDate", () => {
  it("returns em-dash for null", () => {
    expect(formatDate(null)).toBe("\u2014");
  });

  it("returns em-dash for empty string", () => {
    expect(formatDate("")).toBe("\u2014");
  });

  it("formats a valid ISO date", () => {
    const result = formatDate("2024-06-15");
    expect(result).toMatch(/15\.6\.2024/);
  });
});

describe("formatDuration", () => {
  it("returns em-dash for null", () => {
    expect(formatDuration(null)).toBe("\u2014");
  });

  it("formats whole hours", () => {
    expect(formatDuration(3)).toBe("3h 0m");
  });

  it("formats hours with minutes", () => {
    expect(formatDuration(3.5)).toBe("3h 30m");
  });

  it("formats zero hours", () => {
    expect(formatDuration(0)).toBe("0h 0m");
  });
});
