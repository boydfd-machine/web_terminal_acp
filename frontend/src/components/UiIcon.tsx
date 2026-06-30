import type { SVGProps } from "react";

export type UiIconName =
  | "alert-triangle"
  | "branch-plus"
  | "chevron-down"
  | "chevron-left"
  | "chevron-right"
  | "chevron-up"
  | "copy"
  | "download"
  | "edit"
  | "eye"
  | "external-link"
  | "file"
  | "filter-x"
  | "image"
  | "list-tree"
  | "maximize"
  | "message-circle"
  | "plus"
  | "rotate-ccw"
  | "save"
  | "search"
  | "settings"
  | "terminal"
  | "trash"
  | "upload"
  | "x";

export function UiIcon({
  name,
  className = "ui-icon",
  ...props
}: { name: UiIconName } & SVGProps<SVGSVGElement>) {
  const iconProps = {
    className,
    "aria-hidden": true,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props
  };

  switch (name) {
    case "alert-triangle":
      return (
        <svg {...iconProps}>
          <path d="M10.3 4.2 2.5 18a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z" />
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
        </svg>
      );
    case "branch-plus":
      return (
        <svg {...iconProps}>
          <path d="M6 4v6a4 4 0 0 0 4 4h3" />
          <path d="M6 4v16" />
          <path d="M17 10v8" />
          <path d="M13 14h8" />
        </svg>
      );
    case "chevron-down":
      return (
        <svg {...iconProps}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      );
    case "chevron-left":
      return (
        <svg {...iconProps}>
          <path d="m15 18-6-6 6-6" />
        </svg>
      );
    case "chevron-right":
      return (
        <svg {...iconProps}>
          <path d="m9 18 6-6-6-6" />
        </svg>
      );
    case "chevron-up":
      return (
        <svg {...iconProps}>
          <path d="m18 15-6-6-6 6" />
        </svg>
      );
    case "copy":
      return (
        <svg {...iconProps}>
          <rect x="8" y="8" width="11" height="11" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" />
        </svg>
      );
    case "download":
      return (
        <svg {...iconProps}>
          <path d="M12 3v11" />
          <path d="m7 9 5 5 5-5" />
          <path d="M5 20h14" />
        </svg>
      );
    case "edit":
      return (
        <svg {...iconProps}>
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
      );
    case "eye":
      return (
        <svg {...iconProps}>
          <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
          <circle cx="12" cy="12" r="2.8" />
        </svg>
      );
    case "external-link":
      return (
        <svg {...iconProps}>
          <path d="M15 3h6v6" />
          <path d="m10 14 11-11" />
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        </svg>
      );
    case "file":
      return (
        <svg {...iconProps}>
          <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
          <path d="M14 3v6h6" />
          <path d="M8 13h8" />
          <path d="M8 17h5" />
        </svg>
      );
    case "filter-x":
      return (
        <svg {...iconProps}>
          <path d="M4 5h16l-6 7v5l-4 2v-7Z" />
          <path d="m16 16 4 4" />
          <path d="m20 16-4 4" />
        </svg>
      );
    case "image":
      return (
        <svg {...iconProps}>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="8" cy="10" r="1.5" />
          <path d="m21 15-5-5L5 19" />
        </svg>
      );
    case "list-tree":
      return (
        <svg {...iconProps}>
          <path d="M6 3v12" />
          <path d="M6 7h6" />
          <path d="M6 15h6" />
          <path d="M12 7v4" />
          <path d="M12 11h6" />
          <circle cx="6" cy="19" r="2" />
          <circle cx="18" cy="11" r="2" />
        </svg>
      );
    case "maximize":
      return (
        <svg {...iconProps}>
          <path d="M8 3H5a2 2 0 0 0-2 2v3" />
          <path d="M16 3h3a2 2 0 0 1 2 2v3" />
          <path d="M21 16v3a2 2 0 0 1-2 2h-3" />
          <path d="M8 21H5a2 2 0 0 1-2-2v-3" />
        </svg>
      );
    case "message-circle":
      return (
        <svg {...iconProps}>
          <path d="M21 11.5a8.4 8.4 0 0 1-9 8.3 8.6 8.6 0 0 1-4.1-1L3 20l1.3-4.4A8.4 8.4 0 1 1 21 11.5Z" />
          <path d="M8 10h8" />
          <path d="M8 14h5" />
        </svg>
      );
    case "plus":
      return (
        <svg {...iconProps}>
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </svg>
      );
    case "rotate-ccw":
      return (
        <svg {...iconProps}>
          <path d="M3 12a9 9 0 1 0 3-6.7" />
          <path d="M3 4v6h6" />
        </svg>
      );
    case "save":
      return (
        <svg {...iconProps}>
          <path d="M5 3h12l2 2v16H5Z" />
          <path d="M8 3v6h8V3" />
          <path d="M8 21v-7h8v7" />
        </svg>
      );
    case "search":
      return (
        <svg {...iconProps}>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.6-3.6" />
        </svg>
      );
    case "settings":
      return (
        <svg {...iconProps}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1h.2a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1Z" />
        </svg>
      );
    case "terminal":
      return (
        <svg {...iconProps}>
          <path d="M4 5h16v11H4Z" />
          <path d="m8 9 3 3-3 3" />
          <path d="M13 15h4" />
          <path d="M8 20h8" />
        </svg>
      );
    case "trash":
      return (
        <svg {...iconProps}>
          <path d="M4 7h16" />
          <path d="M10 11v6" />
          <path d="M14 11v6" />
          <path d="M6 7l1 13h10l1-13" />
          <path d="M9 7V4h6v3" />
        </svg>
      );
    case "upload":
      return (
        <svg {...iconProps}>
          <path d="M12 21V10" />
          <path d="m7 15 5-5 5 5" />
          <path d="M5 4h14" />
        </svg>
      );
    case "x":
      return (
        <svg {...iconProps}>
          <path d="M18 6 6 18" />
          <path d="m6 6 12 12" />
        </svg>
      );
  }
}
