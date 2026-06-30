import type { ReactNode } from "react";

import type { SearchMatch } from "../types";

export function highlightedText(
  text: string,
  matches: SearchMatch[],
  className = "search-highlight"
): ReactNode {
  return highlightedTextSegments(
    text,
    matches.filter((match) => match.field === "body"),
    className
  );
}

function highlightedTextSegments(
  text: string,
  matches: { start: number; end: number }[],
  className: string
): ReactNode {
  const validMatches = matches
    .filter((match) => match.start >= 0 && match.end > match.start)
    .sort((left, right) => left.start - right.start);
  if (validMatches.length === 0) {
    return text;
  }

  const nodes: ReactNode[] = [];
  let cursor = 0;
  validMatches.forEach((match, index) => {
    const start = Math.max(cursor, Math.min(match.start, text.length));
    const end = Math.max(start, Math.min(match.end, text.length));
    if (start > cursor) {
      nodes.push(text.slice(cursor, start));
    }
    if (end > start) {
      nodes.push(<mark key={`${start}-${end}-${index}`} className={className}>{text.slice(start, end)}</mark>);
    }
    cursor = end;
  });
  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}

export function highlightedFieldText(
  text: string,
  matches: { field: string; start: number; end: number }[],
  field: string,
  className = "search-highlight"
): ReactNode {
  return highlightedTextSegments(
    text,
    matches.filter((match) => match.field === field),
    className
  );
}
