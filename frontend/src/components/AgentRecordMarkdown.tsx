import {
  Children,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode
} from "react";
import DOMPurify from "dompurify";
import type { Mermaid, RenderResult } from "mermaid";
import ReactMarkdown, { defaultUrlTransform, type Components, type UrlTransform } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { useI18n } from "../i18n";
import {
  dispatchProjectFileOpenRequest,
  projectFileLinkHref,
  projectFileRouteRequestFromUrl,
  type ProjectFileLinkContext
} from "../projectFileLinks";

let mermaidPromise: Promise<Mermaid> | null = null;
const DOMPURIFY_MERMAID_SVG_TAGS = ["foreignobject"];
const DOMPURIFY_MERMAID_SVG_ATTRS = ["dominant-baseline"];

function loadMermaid(): Promise<Mermaid> {
  if (mermaidPromise === null) {
    mermaidPromise = import("mermaid").then((module) => {
      module.default.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "dark"
      });
      return module.default;
    });
  }
  return mermaidPromise;
}

function markdownComponents(projectFileContext?: ProjectFileLinkContext | null): Components {
  return {
    a({ node: _node, href, children, ...props }) {
      if (!href) {
        return <span className="agent-event-markdown-link-text">{children}</span>;
      }
      const projectFileHref = projectFileLinkHref(href, projectFileContext);
      if (projectFileHref !== null) {
        return (
          <a
            {...props}
            href={projectFileHref}
            onClick={(event) => {
              const request = projectFileRouteRequestFromUrl(projectFileHref);
              if (request === null) {
                return;
              }
              event.preventDefault();
              dispatchProjectFileOpenRequest(request);
            }}
          >
            {children}
          </a>
        );
      }
      return <a {...props} href={href} target="_blank" rel="noreferrer">{children}</a>;
    },
    img({ node: _node, alt, ...props }) {
      return <img {...props} alt={alt ?? ""} loading="lazy" decoding="async" />;
    },
    table({ node: _node, children, ...props }) {
      return (
        <div className="agent-event-markdown-table-wrap">
          <table {...props}>{children}</table>
        </div>
      );
    },
    pre({ node: _node, children, ...props }) {
      const mermaidSource = mermaidSourceFromPreChildren(children);
      if (mermaidSource !== null) {
        return <MermaidDiagram chart={mermaidSource} />;
      }
      return <pre {...props}>{children}</pre>;
    }
  };
}

function markdownUrlTransform(projectFileContext?: ProjectFileLinkContext | null): UrlTransform {
  return (url) => defaultUrlTransform(url) || (projectFileLinkHref(url, projectFileContext) === null ? undefined : url);
}

export function MarkdownText({
  className,
  projectFileContext,
  text
}: {
  className?: string;
  projectFileContext?: ProjectFileLinkContext | null;
  text: string;
}) {
  const markdownClassName = ["agent-event-markdown", className].filter(Boolean).join(" ");
  return (
    <div className={markdownClassName}>
      <ReactMarkdown
        components={markdownComponents(projectFileContext)}
        remarkPlugins={[remarkGfm, remarkBreaks]}
        urlTransform={markdownUrlTransform(projectFileContext)}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

type MermaidState =
  | { status: "loading" }
  | { status: "ready"; result: RenderResult }
  | { status: "error" };

function MermaidDiagram({ chart }: { chart: string }) {
  const { t } = useI18n();
  const diagramId = useId().replace(/[^a-zA-Z0-9_-]/gu, "");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [state, setState] = useState<MermaidState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    loadMermaid()
      .then((mermaid) => mermaid.render(`agent-markdown-mermaid-${diagramId}`, chart))
      .then((result) => {
        if (!cancelled) {
          setState({ status: "ready", result });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [chart, diagramId]);

  useEffect(() => {
    if (state.status !== "ready" || containerRef.current === null) {
      return;
    }
    state.result.bindFunctions?.(containerRef.current);
  }, [state]);

  if (state.status === "loading") {
    return (
      <div className="agent-event-markdown-mermaid agent-event-markdown-mermaid-loading">
        {t("markdown.mermaidLoading")}
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="agent-event-markdown-mermaid-error" role="group" aria-label={t("markdown.mermaidFailed")}>
        <span>{t("markdown.mermaidFailed")}</span>
        <pre><code className="language-mermaid">{chart}</code></pre>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="agent-event-markdown-mermaid"
      role="img"
      aria-label={t("markdown.mermaidDiagram")}
      dangerouslySetInnerHTML={{ __html: sanitizeMermaidSvg(state.result.svg) }}
    />
  );
}

function sanitizeMermaidSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    ADD_TAGS: DOMPURIFY_MERMAID_SVG_TAGS,
    ADD_ATTR: DOMPURIFY_MERMAID_SVG_ATTRS,
    HTML_INTEGRATION_POINTS: { foreignobject: true }
  });
}

type CodeElementProps = {
  className?: string;
  children?: ReactNode;
};

function mermaidSourceFromPreChildren(children: ReactNode): string | null {
  const childNodes = Children.toArray(children);
  if (childNodes.length !== 1 || !isValidElement<CodeElementProps>(childNodes[0])) {
    return null;
  }
  const codeNode = childNodes[0];
  if (codeNode.type !== "code" || !/\blanguage-mermaid\b/u.test(codeNode.props.className ?? "")) {
    return null;
  }
  const source = reactNodeText(codeNode.props.children).trim();
  return source.length > 0 ? source : null;
}

function reactNodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(reactNodeText).join("");
  }
  return "";
}
