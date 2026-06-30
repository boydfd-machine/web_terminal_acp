import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { THEME_SKINS } from "../src/themeSkins";
import { readFrontendCss } from "./cssTestUtils";

const testDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(testDir, "..");
const stylesCss = readFrontendCss("src/styles.css");
const coverageCss = readFrontendCss("src/themeSkinCoverage.css");
const mainSource = readFileSync(resolve(frontendRoot, "src/main.tsx"), "utf8");

const requiredSkinTokens = [
  "--skin-color-scheme",
  "--skin-control",
  "--skin-control-hover",
  "--skin-selected",
  "--skin-focus-ring",
  "--skin-code-bg",
  "--skin-code-text",
  "--skin-success-soft",
  "--skin-success-text",
  "--skin-warning-soft",
  "--skin-warning-text",
  "--skin-danger-text"
];

function cssClassBlock(cssClass: string): string {
  const match = stylesCss.match(new RegExp(`\\.${cssClass}\\s*\\{([\\s\\S]*?)\\n\\}`, "m"));
  return match?.[1] ?? "";
}

function cssRuleBody(css: string, selector: string): string {
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (match[1].includes(selector)) {
      return match[2];
    }
  }
  return "";
}

function exactCssRuleBody(css: string, selector: string): string {
  const normalizedSelector = selector.replace(/\s+/g, " ").trim();
  for (const match of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (match[1].replace(/\s+/g, " ").trim() === normalizedSelector) {
      return match[2];
    }
  }
  return "";
}

describe("theme skin style coverage", () => {
  it("defines the semantic tokens used by the late coverage layer for every skin", () => {
    for (const skin of THEME_SKINS) {
      const block = cssClassBlock(skin.cssClass);
      expect(block, `${skin.id} has a CSS block`).not.toBe("");
      for (const token of requiredSkinTokens) {
        expect(block, `${skin.id} defines ${token}`).toContain(token);
      }
    }
  });

  it("loads the skin coverage stylesheet after the base stylesheet", () => {
    const baseImportIndex = mainSource.indexOf('import "./styles.css";');
    const coverageImportIndex = mainSource.indexOf('import "./themeSkinCoverage.css";');

    expect(baseImportIndex).toBeGreaterThanOrEqual(0);
    expect(coverageImportIndex).toBeGreaterThan(baseImportIndex);
  });

  it("keeps broad app surfaces under the shared theme scope", () => {
    for (const skin of THEME_SKINS) {
      expect(coverageCss, `${skin.id} participates in the shared coverage layer`).toContain(`.${skin.cssClass}`);
    }

    for (const selector of [
      ".project-todo-card",
      ".project-todo-column",
      ".project-files-view",
      ".settings-modal",
      ".terminal-switcher-panel",
      ".agent-record-modal",
      ".mobile-shortcut-fab"
    ]) {
      expect(coverageCss, `${selector} is themed`).toContain(selector);
    }
  });

  it("preserves project todo board drop highlights in the late theme coverage layer", () => {
    const themedColumnIndex = coverageCss.indexOf(".project-todo-column,");
    const dropAvailableIndex = coverageCss.indexOf(".project-todo-column.drop-available");
    const dropTargetIndex = coverageCss.indexOf(".project-todo-column.drop-target");

    expect(dropAvailableIndex).toBeGreaterThan(themedColumnIndex);
    expect(dropTargetIndex).toBeGreaterThan(dropAvailableIndex);
    expect(coverageCss.slice(dropAvailableIndex, dropTargetIndex)).toContain("background: var(--skin-selected)");
    expect(coverageCss.slice(dropTargetIndex)).toContain("border-color: var(--skin-accent-strong)");
  });

  it("preserves semantic work status badge colors after generic theme coverage", () => {
    const genericBadgeIndex = coverageCss.indexOf(".work-status-badge,");
    expect(genericBadgeIndex).toBeGreaterThanOrEqual(0);

    for (const selector of [
      ".work-status-badge.gray",
      ".work-status-badge.green",
      ".work-status-badge.orange",
      ".work-status-badge.red"
    ]) {
      const toneIndex = coverageCss.indexOf(selector);
      expect(toneIndex, `${selector} has a late tone override`).toBeGreaterThan(genericBadgeIndex);
    }
  });

  it("keeps kanban card selected and editable text surfaces neutral", () => {
    const baseSelectedCard = cssRuleBody(stylesCss, ".project-todo-card.selected");
    const themedSelectedCard = cssRuleBody(coverageCss, ".project-todo-card.selected");
    const genericFocusIndex = coverageCss.indexOf(":is(button:hover:not(:disabled), input:focus, select:focus, textarea:focus)");
    const neutralEditIndex = coverageCss.indexOf(".project-todo-description-edit-form textarea", genericFocusIndex);
    const neutralEditRule = cssRuleBody(
      coverageCss.slice(neutralEditIndex),
      ".project-todo-title-edit-form .project-todo-title-input"
    );

    expect(baseSelectedCard).toContain("background:");
    expect(coverageCss).toContain(".project-todo-card.selected");
    expect(coverageCss).toContain(".project-todo-card-main");
    expect(themedSelectedCard).toContain("background: var(--skin-panel-raised)");
    expect(themedSelectedCard).not.toContain("var(--skin-selected)");
    expect(neutralEditIndex).toBeGreaterThan(genericFocusIndex);
    expect(neutralEditRule).toContain("background: transparent");
    expect(neutralEditRule).toContain("outline-color: var(--skin-muted)");
    expect(neutralEditRule).toContain("box-shadow: none");
  });

  it("keeps the project todo description editor aligned with the read-only panel", () => {
    const sharedPanelRule = cssRuleBody(stylesCss, ".project-todo-detail-description-panel");
    const editFormRule = exactCssRuleBody(stylesCss, ".project-todo-description-edit-form");
    const sharedTextRule = exactCssRuleBody(
      stylesCss,
      ".project-todo-detail-description,\n.project-todo-description-edit-form textarea"
    );
    const cancelButtonRule = exactCssRuleBody(stylesCss, ".project-todo-description-cancel-edit-button");

    expect(sharedPanelRule).toContain("border:");
    expect(editFormRule).toContain("display: block");
    expect(editFormRule).toContain("padding: 0");
    expect(editFormRule).not.toContain("grid-template-rows");
    expect(sharedTextRule).toContain("padding: 12px");
    expect(sharedTextRule).toContain("font-size: 13px");
    expect(sharedTextRule).toContain("line-height: 1.5");
    expect(sharedTextRule).toContain("white-space: pre-wrap");
    expect(cancelButtonRule).toContain("position: absolute");
    expect(cancelButtonRule).toContain("right: 8px");
    expect(cancelButtonRule).toContain("bottom: 8px");
  });

  it("keeps the project todo title editor input transparent after skin control theming", () => {
    const baseTitleEditorRule = cssRuleBody(stylesCss, ".project-todo-title-edit-form input");
    const baseTitleButtonRule = cssRuleBody(stylesCss, ".project-todo-title-button");
    const genericControlIndex = coverageCss.indexOf(":is(button, input, select, textarea)");
    const genericFocusIndex = coverageCss.indexOf(":is(button:hover:not(:disabled), input:focus, select:focus, textarea:focus)");
    const titleEditorIndex = coverageCss.indexOf(".project-todo-title-edit-form .project-todo-title-input");
    const titleEditorRule = cssRuleBody(coverageCss, ".project-todo-title-edit-form .project-todo-title-input");
    const titleButtonIndex = coverageCss.indexOf(".project-todo-title-button", genericFocusIndex);
    const titleButtonRule = cssRuleBody(coverageCss.slice(titleButtonIndex), ".project-todo-title-button");

    expect(baseTitleEditorRule).toContain("background: transparent");
    expect(baseTitleButtonRule).toContain("background: transparent");
    expect(titleEditorIndex).toBeGreaterThan(genericControlIndex);
    expect(titleEditorIndex).toBeGreaterThan(genericFocusIndex);
    expect(titleEditorRule).toContain("background: transparent");
    expect(titleEditorRule).toContain("background-color: transparent");
    expect(titleEditorRule).toContain("border-color: transparent");
    expect(titleEditorRule).toContain("box-shadow: none");
    expect(titleButtonIndex).toBeGreaterThan(genericControlIndex);
    expect(titleButtonIndex).toBeGreaterThan(genericFocusIndex);
    expect(titleButtonRule).toContain("background: transparent");
    expect(titleButtonRule).toContain("background-color: transparent");
    expect(titleButtonRule).toContain("border-color: transparent");
    expect(titleButtonRule).toContain("box-shadow: none");
  });

  it("keeps the workspace mode toggle styled as a compact segmented control", () => {
    const baseToggleRule = cssRuleBody(stylesCss, ".workspace-mode-toggle");
    const baseButtonRule = cssRuleBody(stylesCss, ".workspace-mode-toggle button");
    const baseActiveRule = cssRuleBody(stylesCss, ".workspace-mode-toggle button.active");
    const baseHoverRule = cssRuleBody(stylesCss, ".workspace-mode-toggle button:hover:not(:disabled)");
    const baseFocusRule = cssRuleBody(stylesCss, ".workspace-mode-toggle button:focus-visible:not(:disabled)");
    const themedToggleRule = cssRuleBody(coverageCss, ".workspace-mode-toggle");
    const themedButtonRule = cssRuleBody(coverageCss, ".workspace-mode-toggle button");
    const themedFocusRule = cssRuleBody(coverageCss, ".workspace-mode-toggle button:focus-visible:not(:disabled)");
    const themedActiveHoverRule = cssRuleBody(coverageCss, ".workspace-mode-toggle button.active:hover:not(:disabled)");

    expect(baseToggleRule).toContain("gap: 2px");
    expect(baseToggleRule).toContain("padding: 2px");
    expect(baseToggleRule).toContain("box-shadow:");
    expect(baseButtonRule).toContain("display: inline-flex");
    expect(baseButtonRule).toMatch(/font-weight:\s*(500|var\(--skin-weight-medium\))/);
    expect(baseActiveRule).toContain("box-shadow:");
    expect(baseHoverRule).toContain("border-color:");
    expect(baseFocusRule).toContain("outline: none");
    expect(themedToggleRule).toContain("background: var(--skin-panel)");
    expect(themedButtonRule).toContain("background: transparent");
    expect(themedFocusRule).toContain("box-shadow: 0 0 0 2px var(--skin-focus-ring)");
    expect(themedActiveHoverRule).toContain("border-color: var(--skin-accent)");
    expect(themedActiveHoverRule).toContain("background: var(--skin-selected-hover)");
    expect(themedActiveHoverRule).toContain("box-shadow: inset 0 0 0 1px var(--skin-focus-ring)");
    expect(stylesCss).toContain("grid-template-columns: repeat(3, minmax(0, 1fr));");
  });

  it("keeps token usage progress colors aligned with the active skin", () => {
    const progressRule = cssRuleBody(stylesCss, ".token-usage-progress");
    const warningRule = cssRuleBody(stylesCss, ".token-usage-progress.warning");
    const warningZoneRule = cssRuleBody(stylesCss, ".token-usage-progress-warning-zone");
    const fillRule = cssRuleBody(stylesCss, ".token-usage-progress-fill");

    expect(progressRule).toContain("border: 1px solid var(--skin-border-soft)");
    expect(progressRule).toContain("background: var(--skin-panel)");
    expect(progressRule).not.toContain("rgb(15 23 42");
    expect(warningRule).toContain("border-color: var(--skin-danger)");
    expect(warningRule).toContain("box-shadow: 0 0 0 1px var(--skin-danger-soft)");
    expect(warningZoneRule).toContain("border-left: 1px solid var(--skin-danger)");
    expect(warningZoneRule).toContain("background: var(--skin-danger-soft)");
    expect(fillRule).toContain("background: linear-gradient(90deg, var(--skin-accent), var(--skin-accent-strong))");
  });
});
