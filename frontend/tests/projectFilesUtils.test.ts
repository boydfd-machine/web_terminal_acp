import { describe, expect, it } from "vitest";

import {
  childPath,
  extensionFor,
  isHtml,
  isImage,
  isMarkdown
} from "../src/components/projectFilesUtils";

describe("projectFilesUtils extension helpers", () => {
  describe("extensionFor", () => {
    it("returns the lowercased extension including the leading dot", () => {
      expect(extensionFor("README.md")).toBe(".md");
      expect(extensionFor("index.HTML")).toBe(".html");
      expect(extensionFor("src/site/index.xhtml")).toBe(".xhtml");
    });

    it("returns an empty string when no extension is present", () => {
      expect(extensionFor("README")).toBe("");
      expect(extensionFor("docs/README")).toBe("");
    });
  });

  describe("isMarkdown", () => {
    it.each([".md", ".markdown", ".MD"])("treats %s as markdown", (ext) => {
      expect(isMarkdown(`docs/guide${ext}`)).toBe(true);
    });

    it("returns false for non-markdown extensions", () => {
      expect(isMarkdown("site/index.html")).toBe(false);
      expect(isMarkdown("README")).toBe(false);
    });
  });

  describe("isHtml", () => {
    it.each([".html", ".htm", ".xhtml", ".HTML", ".Htm"])("treats %s as HTML", (ext) => {
      expect(isHtml(`site/index${ext}`)).toBe(true);
    });

    it("returns false for non-HTML extensions", () => {
      expect(isHtml("README.md")).toBe(false);
      expect(isHtml("index.txt")).toBe(false);
      expect(isHtml("index")).toBe(false);
    });
  });

  describe("isImage", () => {
    it.each([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".avif", ".PNG", ".Jpeg"])(
      "treats %s as an image",
      (ext) => {
        expect(isImage(`assets/logo${ext}`)).toBe(true);
      }
    );

    it("returns false for non-image extensions", () => {
      expect(isImage("README.md")).toBe(false);
      expect(isImage("index.html")).toBe(false);
      expect(isImage("archive.zip")).toBe(false);
      expect(isImage("logo")).toBe(false);
    });
  });

  describe("childPath", () => {
    it("joins the parent path with the child name", () => {
      expect(childPath("docs", "guide.md")).toBe("docs/guide.md");
    });

    it("returns the name directly when the parent is the root path", () => {
      expect(childPath(".", "README.md")).toBe("README.md");
    });
  });
});
