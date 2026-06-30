import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const testDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(testDir, "..");

export function readFrontendCss(relativePath: string): string {
  const absolutePath = resolve(frontendRoot, relativePath);
  const css = readFileSync(absolutePath, "utf8");
  const fileDir = dirname(absolutePath);

  return css.replace(/@import\s+"([^"]+)";/g, (_match, importPath: string) => {
    const importedPath = resolve(fileDir, importPath);
    const importedRelativePath = importedPath.slice(frontendRoot.length + 1);
    return readFrontendCss(importedRelativePath);
  });
}

export function cssRuleBody(css: string, selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`(?:^|\\n)${escapedSelector}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match) {
    throw new Error(`Missing CSS rule for ${selector}`);
  }
  return match[1];
}

export function cssRuleBodies(css: string, selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return Array.from(css.matchAll(new RegExp(`(?:^|\\n)${escapedSelector}\\s*\\{([^}]*)\\}`, "g")))
    .map((match) => match[1])
    .join("\n");
}
