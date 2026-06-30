import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent
} from "react";

import { useI18n } from "../i18n";
import type { ProjectTodoListItem } from "../types";
import {
  PROJECT_TODO_STATUS_LABELS,
  projectTodoStatusLabel,
  projectTodoStatusClass
} from "./projectTodoDisplay";

type ActiveMention = {
  start: number;
  query: string;
};

type MentionSearchState = {
  start: number;
  mentionQuery: string;
  query: string;
};

type SearchFocusRequest = {
  start: number;
  sequence: number;
};

type TextareaSelection = {
  start: number;
  end: number;
};

type ProjectTodoMentionTodo = Pick<ProjectTodoListItem, "id" | "title" | "status"> & {
  description?: string | null;
};

type ProjectTodoDescriptionMentionTextareaProps = {
  value: string;
  todos: ProjectTodoMentionTodo[];
  currentTodoId?: string | null;
  ariaLabel?: string;
  autoResize?: boolean;
  autoFocus?: boolean;
  disabled?: boolean;
  maxLength?: number;
  placeholder?: string;
  rows?: number;
  onChange: (description: string) => void;
};

const MAX_SUGGESTIONS = 8;

export function ProjectTodoDescriptionMentionTextarea({
  value,
  todos,
  currentTodoId = null,
  ariaLabel,
  autoResize = false,
  autoFocus = false,
  disabled = false,
  maxLength,
  placeholder,
  rows,
  onChange
}: ProjectTodoDescriptionMentionTextareaProps) {
  const { t } = useI18n();
  const fieldRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const textareaSelectionRef = useRef<TextareaSelection>({ start: value.length, end: value.length });
  const searchFocusSequenceRef = useRef(0);
  const menuId = useId();
  const [cursor, setCursor] = useState(value.length);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [searchState, setSearchState] = useState<MentionSearchState | null>(null);
  const [searchFocusRequest, setSearchFocusRequest] = useState<SearchFocusRequest | null>(null);
  const mention = activeProjectTodoMention(value, cursor);
  const searchQuery = mention === null
    ? ""
    : searchState !== null
      && searchState.start === mention.start
      && searchState.mentionQuery === mention.query
      ? searchState.query
      : mention.query;
  const suggestions = useMemo(() => {
    if (mention === null) {
      return [];
    }
    return projectTodoMentionSuggestions(todos, currentTodoId, searchQuery);
  }, [currentTodoId, mention, searchQuery, todos]);
  const menuOpen = open && mention !== null;

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (textarea === null) {
      return;
    }
    if (!autoResize) {
      textarea.style.height = "";
      return;
    }
    textarea.style.height = "auto";
    const form = fieldRef.current?.parentElement;
    const formHeight = form instanceof HTMLElement ? form.clientHeight : 0;
    const maxHeight = form instanceof HTMLElement
      ? Number.parseFloat(window.getComputedStyle(form).maxHeight)
      : Number.NaN;
    const targetHeight = Math.max(textarea.scrollHeight, formHeight, 1);
    textarea.style.height = `${Number.isFinite(maxHeight) ? Math.min(targetHeight, maxHeight) : targetHeight}px`;
  }, [autoResize, value]);

  useEffect(() => {
    setActiveIndex(0);
  }, [searchQuery, suggestions.length]);

  useEffect(() => {
    if (!menuOpen) {
      setSearchState(null);
      setSearchFocusRequest(null);
    }
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen || mention === null || searchFocusRequest === null) {
      return;
    }
    if (mention.start !== searchFocusRequest.start || mention.query.length > 0) {
      return;
    }
    const focusSearch = () => {
      searchInputRef.current?.focus({ preventScroll: true });
      searchInputRef.current?.select();
      setSearchFocusRequest((current) => (
        current?.sequence === searchFocusRequest.sequence ? null : current
      ));
    };
    if (typeof window.requestAnimationFrame === "function") {
      const frame = window.requestAnimationFrame(focusSearch);
      return () => window.cancelAnimationFrame(frame);
    }
    const timeout = window.setTimeout(focusSearch, 0);
    return () => window.clearTimeout(timeout);
  }, [menuOpen, mention, searchFocusRequest]);

  const updateCursor = (textarea: HTMLTextAreaElement) => {
    textareaSelectionRef.current = {
      start: textarea.selectionStart,
      end: textarea.selectionEnd
    };
    setCursor(textarea.selectionStart);
    setOpen(true);
  };

  const shouldFocusSearchAfterTextareaChange = (
    nextValue: string,
    nextCursor: number
  ): ActiveMention | null => {
    const nextMention = activeProjectTodoMention(nextValue, nextCursor);
    if (nextMention === null || nextMention.query.length > 0) {
      return null;
    }

    const previousCursor = Math.max(textareaSelectionRef.current.start, textareaSelectionRef.current.end);
    const previousMention = activeProjectTodoMention(value, previousCursor);
    if (
      previousMention === null
      || previousMention.start !== nextMention.start
      || previousMention.query.length > 0
    ) {
      return nextMention;
    }
    return null;
  };

  const requestSearchFocus = (activeMention: ActiveMention) => {
    searchFocusSequenceRef.current += 1;
    setSearchFocusRequest({
      start: activeMention.start,
      sequence: searchFocusSequenceRef.current
    });
  };

  const closeIfFocusLeaves = () => {
    window.setTimeout(() => {
      if (!fieldRef.current?.contains(document.activeElement)) {
        setOpen(false);
      }
    }, 0);
  };

  const insertReference = (todo: ProjectTodoMentionTodo) => {
    const textarea = textareaRef.current;
    const nextCursor = textarea?.selectionStart ?? cursor;
    const activeMention = activeProjectTodoMention(value, nextCursor);
    if (activeMention === null) {
      return;
    }

    const token = projectTodoReferenceToken(todo);
    const before = value.slice(0, activeMention.start);
    const after = value.slice(nextCursor);
    const spacer = after.length === 0 || /^[\s.,;:!?，。；：！？]/u.test(after) ? "" : " ";
    const nextValue = `${before}${token}${spacer}${after}`;
    const nextSelection = before.length + token.length + spacer.length;
    onChange(nextValue);
    setCursor(nextSelection);
    setOpen(false);
    const restoreSelection = () => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(nextSelection, nextSelection);
    };
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(restoreSelection);
    } else {
      window.setTimeout(restoreSelection, 0);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    if (!menuOpen) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      textareaRef.current?.focus();
      return;
    }
    if (suggestions.length === 0) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % suggestions.length);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current - 1 + suggestions.length) % suggestions.length);
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      insertReference(suggestions[activeIndex] ?? suggestions[0]);
    }
  };

  return (
    <div ref={fieldRef} className="project-todo-description-mention-field">
      <textarea
        ref={textareaRef}
        value={value}
        aria-autocomplete="list"
        aria-controls={menuOpen ? menuId : undefined}
        aria-expanded={menuOpen}
        aria-label={ariaLabel}
        autoFocus={autoFocus}
        disabled={disabled}
        maxLength={maxLength}
        placeholder={placeholder}
        rows={rows}
        onBlur={closeIfFocusLeaves}
        onChange={(event) => {
          const mentionFocus = shouldFocusSearchAfterTextareaChange(
            event.target.value,
            event.target.selectionStart
          );
          onChange(event.target.value);
          updateCursor(event.target);
          if (mentionFocus !== null) {
            requestSearchFocus(mentionFocus);
          }
        }}
        onClick={(event) => updateCursor(event.currentTarget)}
        onFocus={(event) => updateCursor(event.currentTarget)}
        onKeyDown={handleKeyDown}
        onSelect={(event) => updateCursor(event.currentTarget)}
        onKeyUp={(event) => updateCursor(event.currentTarget)}
      />
      {menuOpen && (
        <div id={menuId} className="project-todo-mention-menu" role="listbox">
          <input
            ref={searchInputRef}
            className="project-todo-mention-search"
            type="search"
            value={searchQuery}
            aria-label={t("projectTodo.description.searchCards")}
            placeholder={t("projectTodo.description.searchCards")}
            onBlur={closeIfFocusLeaves}
            onChange={(event) => {
              if (mention !== null) {
                setSearchState({
                  start: mention.start,
                  mentionQuery: mention.query,
                  query: event.target.value
                });
              }
            }}
            onKeyDown={handleKeyDown}
          />
          {suggestions.length === 0 ? (
            <div className="project-todo-mention-empty">{t("projectTodo.description.noMatches")}</div>
          ) : suggestions.map((todo, index) => (
            <button
              key={todo.id}
              type="button"
              className={`project-todo-mention-option${index === activeIndex ? " active" : ""}`}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => insertReference(todo)}
            >
              <strong>{todo.title}</strong>
              <span className={`project-todo-status-pill ${projectTodoStatusClass(todo.status)}`}>
                {projectTodoStatusLabel(todo.status, t)}
              </span>
              <small>{todo.description?.trim() || t("projectTodo.description.noDescription")}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function projectTodoReferenceToken(todo: Pick<ProjectTodoMentionTodo, "id" | "title">): string {
  return `@[其它需求：$${todo.title}|${todo.id}]`;
}

function activeProjectTodoMention(value: string, cursor: number): ActiveMention | null {
  const prefix = value.slice(0, cursor);
  const start = prefix.lastIndexOf("@");
  if (start < 0) {
    return null;
  }
  const query = prefix.slice(start + 1);
  if (query.startsWith("[") || query.includes("\n") || query.length > 80) {
    return null;
  }
  return { start, query: query.trimStart() };
}

function projectTodoMentionSuggestions(
  todos: ProjectTodoMentionTodo[],
  currentTodoId: string | null,
  query: string
): ProjectTodoMentionTodo[] {
  const normalizedQuery = normalizeProjectTodoMentionText(query);
  return todos
    .filter((todo) => todo.id !== currentTodoId && todo.title.trim().length > 0)
    .filter((todo) => {
      if (normalizedQuery.length === 0) {
        return true;
      }
      return [
        todo.title,
        PROJECT_TODO_STATUS_LABELS[todo.status],
        todo.description ?? ""
      ].some((value) => normalizeProjectTodoMentionText(value).includes(normalizedQuery));
    })
    .slice(0, MAX_SUGGESTIONS);
}

function normalizeProjectTodoMentionText(value: string): string {
  return value.trim().toLowerCase();
}
