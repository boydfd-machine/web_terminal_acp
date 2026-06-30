export type PageAnnotationRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type PageAnnotationElementEvidence = {
  selector: string;
  selectorConfidence: "high" | "medium" | "low";
  tagName: string;
  role: string | null;
  accessibleName: string | null;
  text: string;
  classNames: string[];
  safeAttributes: Record<string, string>;
  rect: PageAnnotationRect;
  style: Record<string, string>;
  ancestry: string[];
};

export type PageAnnotationEvidence = {
  route: string;
  viewport: { width: number; height: number; devicePixelRatio: number };
  selection: PageAnnotationRect;
  primaryTarget: PageAnnotationElementEvidence | null;
  elements: PageAnnotationElementEvidence[];
  appState: {
    workspaceMode: string;
    clientId: string | null;
    projectPath: string | null;
    windowId: string | null;
    themeSkin?: string;
  };
};

type CollectPageAnnotationEvidenceInput = {
  selection: PageAnnotationRect;
  appState: PageAnnotationEvidence["appState"];
};

const STYLE_PROPERTIES = [
  "display", "position", "z-index", "width", "height", "overflow", "gap",
  "flex-direction", "grid-template-columns", "margin-top", "margin-right",
  "margin-bottom", "margin-left", "padding-top", "padding-right",
  "padding-bottom", "padding-left", "border-radius", "border-top-width",
  "border-right-width", "border-bottom-width", "border-left-width",
  "border-top-style", "border-right-style", "border-bottom-style",
  "border-left-style", "border-top-color", "border-right-color",
  "border-bottom-color", "border-left-color", "box-shadow", "font-size",
  "font-weight", "line-height", "color", "background-color", "opacity"
] as const;

export function collectPageAnnotationEvidence(input: CollectPageAnnotationEvidenceInput): PageAnnotationEvidence {
  const candidates = collectCandidateElements(input.selection);
  const ranked = candidates
    .map((element) => ({ element, score: primaryTargetScore(element, input.selection) }))
    .sort((first, second) => second.score - first.score)
    .slice(0, 20);
  const elements = ranked.map(({ element }) => elementEvidence(element));
  return {
    route: `${window.location.pathname}${window.location.search}${window.location.hash}`,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio || 1
    },
    selection: roundRect(input.selection),
    primaryTarget: elements[0] ?? null,
    elements,
    appState: input.appState
  };
}

export function pageAnnotationRectIntersects(first: PageAnnotationRect, second: PageAnnotationRect): boolean {
  return first.left < second.left + second.width
    && first.left + first.width > second.left
    && first.top < second.top + second.height
    && first.top + first.height > second.top;
}

function collectCandidateElements(selection: PageAnnotationRect): HTMLElement[] {
  const candidates = new Set<HTMLElement>();
  const visibleElements = collectVisibleElements(selection);
  if (visibleElements !== null && visibleElements.size > 0) {
    for (const element of visibleElements) {
      if (isEvidenceCandidate(element, selection)) {
        candidates.add(element);
      }
    }
    return Array.from(candidates);
  }
  for (const element of Array.from(document.querySelectorAll("body *"))) {
    const htmlElement = asHtmlElement(element);
    if (htmlElement !== null && isEvidenceCandidate(htmlElement, selection)) {
      candidates.add(htmlElement);
    }
  }
  return Array.from(candidates);
}

function collectVisibleElements(selection: PageAnnotationRect): Set<HTMLElement> | null {
  const elementsFromPoint = typeof document.elementsFromPoint === "function"
    ? document.elementsFromPoint.bind(document)
    : null;
  if (elementsFromPoint === null) {
    return null;
  }
  const visibleElements = new Set<HTMLElement>();
  for (const point of samplePoints(selection)) {
    const topElement = firstAnnotatableElement(elementsFromPoint(point.x, point.y));
    if (topElement !== null) {
      addElementAndAncestors(visibleElements, topElement);
    }
  }
  return visibleElements;
}

function firstAnnotatableElement(elements: Element[]): HTMLElement | null {
  for (const element of elements) {
    const htmlElement = asHtmlElement(element);
    if (htmlElement !== null && !isPageAnnotationUi(htmlElement)) {
      return htmlElement;
    }
  }
  return null;
}

function addElementAndAncestors(elements: Set<HTMLElement>, element: HTMLElement): void {
  let current: HTMLElement | null = element;
  while (current !== null && current !== document.body) {
    if (!isPageAnnotationUi(current)) {
      elements.add(current);
    }
    current = current.parentElement;
  }
}

function asHtmlElement(element: Element): HTMLElement | null {
  if (element instanceof HTMLElement) {
    return element;
  }
  if (
    typeof (element as HTMLElement).getBoundingClientRect === "function"
    && typeof (element as HTMLElement).tagName === "string"
  ) {
    return element as HTMLElement;
  }
  return null;
}

function isEvidenceCandidate(element: HTMLElement, selection: PageAnnotationRect): boolean {
  if (isPageAnnotationUi(element)) {
    return false;
  }
  const rect = rectFromDom(element.getBoundingClientRect());
  return rect.width > 0 && rect.height > 0 && pageAnnotationRectIntersects(selection, rect);
}

function isPageAnnotationUi(element: HTMLElement): boolean {
  return element.closest("[data-page-annotation-ui]") !== null;
}

function primaryTargetScore(element: HTMLElement, selection: PageAnnotationRect): number {
  const rect = rectFromDom(element.getBoundingClientRect());
  const overlap = intersectionArea(selection, rect);
  const elementArea = Math.max(rect.width * rect.height, 1);
  const overlapRatio = overlap / elementArea;
  const semanticBonus = semanticWeight(element);
  const textBonus = normalizeText(element.textContent ?? "").length > 0 ? 8 : 0;
  return overlapRatio * 100 + semanticBonus + textBonus - Math.min(elementArea / 50000, 20);
}

function semanticWeight(element: HTMLElement): number {
  if (element.dataset.debugId !== undefined) {
    return 50;
  }
  if (["BUTTON", "A", "INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)) {
    return 35;
  }
  if (element.getAttribute("role") !== null || element.getAttribute("aria-label") !== null) {
    return 25;
  }
  return 0;
}

function elementEvidence(element: HTMLElement): PageAnnotationElementEvidence {
  const selector = bestSelector(element);
  return {
    selector: selector.value,
    selectorConfidence: selector.confidence,
    tagName: element.tagName.toLowerCase(),
    role: element.getAttribute("role") ?? inferredRole(element),
    accessibleName: accessibleName(element),
    text: elementText(element),
    classNames: Array.from(element.classList).slice(0, 12),
    safeAttributes: safeAttributes(element),
    rect: roundRect(rectFromDom(element.getBoundingClientRect())),
    style: styleSummary(element),
    ancestry: ancestry(element)
  };
}

function bestSelector(element: HTMLElement): { value: string; confidence: "high" | "medium" | "low" } {
  if (element.dataset.debugId) {
    return { value: `[data-debug-id="${escapeAttribute(element.dataset.debugId)}"]`, confidence: "high" };
  }
  if (element.dataset.onboardingId) {
    return { value: `[data-onboarding-id="${escapeAttribute(element.dataset.onboardingId)}"]`, confidence: "high" };
  }
  if (element.id) {
    return { value: `${element.tagName.toLowerCase()}#${escapeSelector(element.id)}`, confidence: "medium" };
  }
  const ariaLabel = element.getAttribute("aria-label");
  if (ariaLabel) {
    return { value: `${element.tagName.toLowerCase()}[aria-label="${escapeAttribute(ariaLabel)}"]`, confidence: "medium" };
  }
  const classes = Array.from(element.classList).filter((className) => !className.includes(":")).slice(0, 3);
  if (classes.length > 0) {
    return { value: `${element.tagName.toLowerCase()}.${classes.map(escapeSelector).join(".")}`, confidence: "medium" };
  }
  return { value: nthSelector(element), confidence: "low" };
}

function safeAttributes(element: HTMLElement): Record<string, string> {
  const attributes: Record<string, string> = {};
  for (const attribute of Array.from(element.attributes)) {
    const name = attribute.name.toLowerCase();
    if (!safeAttributeName(name)) {
      continue;
    }
    const value = sanitizeAttributeValue(name, attribute.value);
    if (value.length > 0) {
      attributes[name] = value;
    }
  }
  return attributes;
}

function safeAttributeName(name: string): boolean {
  if (name === "title" || name === "type" || name === "href") {
    return true;
  }
  if (name.startsWith("aria-")) {
    return true;
  }
  if (!name.startsWith("data-")) {
    return false;
  }
  return !/(token|secret|password|key|auth|credential|session)/i.test(name);
}

function sanitizeAttributeValue(name: string, value: string): string {
  const trimmed = value.trim();
  if (name === "href") {
    return sanitizeHref(trimmed);
  }
  return trimText(trimmed, 160);
}

function sanitizeHref(value: string): string {
  try {
    const url = new URL(value, window.location.origin);
    return `${url.pathname}${url.hash}`;
  } catch {
    return value.split("?")[0].slice(0, 160);
  }
}

function accessibleName(element: HTMLElement): string | null {
  return trimNullable(
    element.getAttribute("aria-label")
    ?? labelledByText(element)
    ?? (element instanceof HTMLImageElement ? element.alt : null)
    ?? (element instanceof HTMLInputElement ? element.placeholder : null)
  );
}

function labelledByText(element: HTMLElement): string | null {
  const labelledBy = element.getAttribute("aria-labelledby");
  if (!labelledBy) {
    return null;
  }
  return labelledBy
    .split(/\s+/)
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
}

function inferredRole(element: HTMLElement): string | null {
  const tag = element.tagName.toLowerCase();
  if (tag === "button") {
    return "button";
  }
  if (tag === "a" && element.hasAttribute("href")) {
    return "link";
  }
  if (tag === "input" || tag === "textarea") {
    return "textbox";
  }
  if (tag === "select") {
    return "combobox";
  }
  return null;
}

function elementText(element: HTMLElement): string {
  if (element.matches(".xterm-screen, .terminal-screen, [data-debug-id='terminal-container'] *")) {
    return "";
  }
  return trimText(normalizeText(element.innerText || element.textContent || ""), 300);
}

function styleSummary(element: HTMLElement): Record<string, string> {
  const computedStyle = window.getComputedStyle(element);
  const summary: Record<string, string> = {};
  for (const property of STYLE_PROPERTIES) {
    const value = computedStyle.getPropertyValue?.(property) || computedStyle[propertyToCamel(property) as keyof CSSStyleDeclaration];
    if (typeof value === "string" && value.trim().length > 0) {
      summary[property] = value.trim();
    }
  }
  return summary;
}

function ancestry(element: HTMLElement): string[] {
  const chain: string[] = [];
  let current: HTMLElement | null = element;
  while (current !== null && current !== document.body && chain.length < 8) {
    chain.unshift(elementLabel(current));
    if (current.matches("main, [data-debug-id='app-shell'], [data-onboarding-id='app-layout']")) {
      break;
    }
    current = current.parentElement;
  }
  return chain;
}

function elementLabel(element: HTMLElement): string {
  const parts = [element.tagName.toLowerCase()];
  if (element.dataset.debugId) {
    parts.push(`[data-debug-id="${escapeAttribute(element.dataset.debugId)}"]`);
  } else if (element.dataset.onboardingId) {
    parts.push(`[data-onboarding-id="${escapeAttribute(element.dataset.onboardingId)}"]`);
  } else if (element.id) {
    parts.push(`#${escapeSelector(element.id)}`);
  } else {
    const classes = Array.from(element.classList).slice(0, 2);
    if (classes.length > 0) {
      parts.push(`.${classes.map(escapeSelector).join(".")}`);
    }
  }
  return parts.join("");
}

function nthSelector(element: HTMLElement): string {
  const parent = element.parentElement;
  if (parent === null) {
    return element.tagName.toLowerCase();
  }
  const siblings = Array.from(parent.children).filter((child) => child.tagName === element.tagName);
  const index = siblings.indexOf(element) + 1;
  return `${element.tagName.toLowerCase()}:nth-of-type(${Math.max(index, 1)})`;
}

function samplePoints(rect: PageAnnotationRect): Array<{ x: number; y: number }> {
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const right = rect.left + rect.width;
  const bottom = rect.top + rect.height;
  return [
    { x: centerX, y: centerY },
    { x: rect.left + 1, y: rect.top + 1 },
    { x: right - 1, y: rect.top + 1 },
    { x: rect.left + 1, y: bottom - 1 },
    { x: right - 1, y: bottom - 1 },
    { x: centerX, y: rect.top + 1 },
    { x: centerX, y: bottom - 1 },
    { x: rect.left + 1, y: centerY },
    { x: right - 1, y: centerY }
  ];
}

function intersectionArea(first: PageAnnotationRect, second: PageAnnotationRect): number {
  const left = Math.max(first.left, second.left);
  const top = Math.max(first.top, second.top);
  const right = Math.min(first.left + first.width, second.left + second.width);
  const bottom = Math.min(first.top + first.height, second.top + second.height);
  return Math.max(0, right - left) * Math.max(0, bottom - top);
}

function rectFromDom(rect: DOMRect): PageAnnotationRect {
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height
  };
}

function roundRect(rect: PageAnnotationRect): PageAnnotationRect {
  return {
    left: Math.round(rect.left),
    top: Math.round(rect.top),
    width: Math.round(rect.width),
    height: Math.round(rect.height)
  };
}

function trimNullable(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  const trimmed = normalizeText(value);
  return trimmed.length > 0 ? trimText(trimmed, 160) : null;
}

function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function trimText(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength - 1)}...`;
}

function escapeSelector(value: string): string {
  return typeof CSS !== "undefined" && typeof CSS.escape === "function"
    ? CSS.escape(value)
    : value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

function escapeAttribute(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function propertyToCamel(property: string): string {
  return property.replace(/-([a-z])/g, (_match, char: string) => char.toUpperCase());
}
