import { describe, expect, it } from "vitest";

import { cssRuleBody, readFrontendCss } from "./cssTestUtils";

const stylesCss = readFrontendCss("src/styles.css");

describe("TerminalSwitcher layout styles", () => {
  it("keeps terminal metadata bounded while preserving title space", () => {
    const rowCss = cssRuleBody(stylesCss, ".switcher-window");
    const rowWithMetaCss = cssRuleBody(stylesCss, ".switcher-window.with-meta");
    const rowWithClientCss = cssRuleBody(stylesCss, ".switcher-window.with-client-name");
    const rowWithClientMetaCss = cssRuleBody(stylesCss, ".switcher-window.with-client-name.with-meta");
    const titleBlockCss = cssRuleBody(stylesCss, ".switcher-window-title-block");
    const clientNameCss = cssRuleBody(stylesCss, ".switcher-client-name");
    const metaCss = cssRuleBody(stylesCss, ".switcher-window-meta");
    const metaWithClientCss = cssRuleBody(stylesCss, ".switcher-window.with-client-name .switcher-window-meta");
    const agentTagCss = cssRuleBody(stylesCss, ".switcher-window-tag.agent");
    const timeCss = cssRuleBody(stylesCss, ".switcher-window-meta-time");
    const projectCss = cssRuleBody(stylesCss, ".switcher-window-meta-project");

    expect(rowCss).toContain("display: grid");
    expect(rowCss).toContain("grid-template-columns: 8px minmax(0, 1fr) 8px");
    expect(rowWithMetaCss).toContain("grid-template-columns: 8px minmax(0, 1fr) 420px 8px");
    expect(rowWithClientCss).toContain("grid-template-columns: 8px minmax(0, 1fr) minmax(86px, 120px) 8px");
    expect(rowWithClientMetaCss).toContain("grid-template-columns: 8px minmax(0, 1fr) minmax(86px, 120px) 360px 8px");
    expect(titleBlockCss).toContain("grid-column: 2");
    expect(titleBlockCss).toContain("width: 100%");
    expect(clientNameCss).toContain("grid-column: 3");
    expect(clientNameCss).toContain("justify-self: stretch");
    expect(clientNameCss).toContain("min-width: 0");
    expect(metaCss).toContain("grid-column: 3");
    expect(metaCss).toContain("display: grid");
    expect(metaCss).toContain("grid-template-columns: 88px 112px minmax(0, 1fr)");
    expect(metaCss).toContain("justify-items: start");
    expect(metaCss).toContain("text-align: left");
    expect(metaWithClientCss).toContain("grid-column: 4");
    expect(metaWithClientCss).toContain("grid-template-columns: 82px 104px minmax(0, 1fr)");
    expect(agentTagCss).toContain("justify-self: start");
    expect(timeCss).toContain("justify-self: start");
    expect(projectCss).toContain("justify-self: start");
    expect(cssRuleBody(stylesCss, ".switcher-window-meta-text")).toContain("text-overflow: ellipsis");
    expect(cssRuleBody(stylesCss, ".switcher-window-meta-text")).toContain("white-space: nowrap");
    expect(stylesCss).toContain(".switcher-window-meta {\n    grid-column: 2 / -1;\n    grid-row: 2;\n    grid-template-columns: max-content max-content minmax(0, 1fr);");
  });
});
