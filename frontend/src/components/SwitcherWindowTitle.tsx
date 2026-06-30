import { useOverflowStatus } from "./useOverflowStatus";

export function compactTodoTitle(title: string, todoTitle: string | null | undefined): string | null {
  const normalized = todoTitle?.trim();
  if (!normalized || normalized === title.trim()) {
    return null;
  }
  return normalized;
}

export function switcherWindowTitle(title: string, todoTitle: string | null | undefined): string {
  const subtitle = compactTodoTitle(title, todoTitle);
  return subtitle === null ? title : `${title}\n${subtitle}`;
}

export function SwitcherWindowTitle({
  active,
  title,
  todoTitle
}: {
  active: boolean;
  title: string;
  todoTitle?: string | null;
}) {
  const subtitle = compactTodoTitle(title, todoTitle);
  const [titleRef, titleOverflowing] = useOverflowStatus<HTMLSpanElement>();
  const [subtitleRef, subtitleOverflowing] = useOverflowStatus<HTMLSpanElement>();
  const fullTitle = switcherWindowTitle(title, todoTitle);
  const showFullTitle = active && (titleOverflowing || subtitleOverflowing);

  return (
    <span className="switcher-window-title-block">
      <span ref={titleRef} className="switcher-window-title">{title}</span>
      {subtitle !== null && <span ref={subtitleRef} className="switcher-window-todo-title">{subtitle}</span>}
      {showFullTitle && <span className="switcher-window-title-tip">{fullTitle}</span>}
    </span>
  );
}
