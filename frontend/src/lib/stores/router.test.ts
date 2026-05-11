import { describe, it, expect } from "vitest";
import { parseHash } from "./router";

describe("parseHash", () => {
  it("parses pipeline route from /", () => {
    expect(parseHash("#/")).toEqual({ page: "pipeline" });
  });

  it("parses pipeline route from empty", () => {
    expect(parseHash("")).toEqual({ page: "pipeline" });
  });

  it("parses pipeline route from /pipeline", () => {
    expect(parseHash("#/pipeline")).toEqual({ page: "pipeline" });
  });

  it("parses articles list", () => {
    expect(parseHash("#/articles")).toEqual({ page: "articles" });
  });

  it("parses article detail", () => {
    expect(parseHash("#/articles/42")).toEqual({ page: "article", id: 42 });
  });

  it("parses draft route", () => {
    expect(parseHash("#/draft/7")).toEqual({ page: "draft", id: 7 });
  });

  it("parses photobooks list", () => {
    expect(parseHash("#/photobooks")).toEqual({ page: "photobooks" });
  });

  it("parses photobook detail", () => {
    expect(parseHash("#/photobooks/3")).toEqual({ page: "photobook", id: 3 });
  });

  it("falls back to pipeline for unknown routes", () => {
    expect(parseHash("#/unknown")).toEqual({ page: "pipeline" });
  });
});
