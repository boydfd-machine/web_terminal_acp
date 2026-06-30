import { useEffect, useId, useMemo, useRef, useState } from "react";

import { UiIcon } from "./UiIcon";

export type ProjectTodoMultiSelectSearchItem = {
  key: string;
  label: string;
  searchText: string;
  value: string;
  description?: string;
};

type ProjectTodoMultiSelectSearchFieldProps = {
  items: ProjectTodoMultiSelectSearchItem[];
  selectedValues: string[];
  allSelectedLabel: string;
  className: string;
  emptyLabel: string;
  legend: string;
  noSelectionLabel: string;
  removeLabel: (label: string) => string;
  searchLabel: string;
  selectedItemsLabel: string;
  onSelectionChange: (values: string[]) => void;
  addLabel?: string;
  disabled?: boolean;
  errorLabel?: string | null;
  loading?: boolean;
  loadingLabel?: string;
  openWhenEmpty?: boolean;
  onOpen?: () => void;
};

export function ProjectTodoMultiSelectSearchField({
  items,
  selectedValues,
  addLabel,
  allSelectedLabel,
  className,
  disabled = false,
  emptyLabel,
  errorLabel = null,
  legend,
  loading = false,
  loadingLabel,
  noSelectionLabel,
  openWhenEmpty = false,
  removeLabel,
  searchLabel,
  selectedItemsLabel,
  onOpen,
  onSelectionChange
}: ProjectTodoMultiSelectSearchFieldProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const menuId = useId();
  const rootRef = useRef<HTMLFieldSetElement | null>(null);
  const itemByValue = useMemo(() => new Map(items.map((item) => [item.value, item])), [items]);
  const selectedItems = selectedValues.map((value) => itemByValue.get(value) ?? fallbackItem(value));
  const selectedValueSet = useMemo(() => new Set(selectedValues), [selectedValues]);
  const availableItems = items.filter((item) => !selectedValueSet.has(item.value));
  const normalizedSearchQuery = searchQuery.trim().toLowerCase();
  const visibleItems = normalizedSearchQuery.length === 0
    ? availableItems
    : availableItems.filter((item) => item.searchText.includes(normalizedSearchQuery));
  const selectedLabels = selectedItems.map((item) => item.label);
  const selectPlaceholder = selectedItems.length > 0
    ? availableItems.length > 0
      ? addLabel ?? searchLabel
      : allSelectedLabel
    : noSelectionLabel;
  const canOpen = !disabled && (
    loading
    || availableItems.length > 0
    || (openWhenEmpty && (errorLabel !== null || items.length === 0))
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  useEffect(() => {
    if (disabled) {
      setOpen(false);
    }
  }, [disabled]);

  useEffect(() => {
    if (!open) {
      setSearchQuery("");
    }
  }, [open]);

  useEffect(() => {
    if (open && availableItems.length === 0 && !loading && !openWhenEmpty) {
      setOpen(false);
    }
  }, [availableItems.length, loading, open, openWhenEmpty]);

  const requestOpen = () => {
    if (disabled) {
      return;
    }
    onOpen?.();
    if (canOpen) {
      setOpen(true);
    }
  };

  return (
    <fieldset className={className} aria-label={legend} ref={rootRef}>
      <legend>{legend}</legend>
      {selectedItems.length > 0 && (
        <div className="project-todo-artifact-selected-list" aria-label={selectedItemsLabel}>
          {selectedItems.map((item) => (
            <span key={item.key} className="project-todo-artifact-selected-chip" title={item.value}>
              <span>{item.label}</span>
              <button
                type="button"
                disabled={disabled}
                aria-label={removeLabel(item.label)}
                title={removeLabel(item.label)}
                onClick={() => onSelectionChange(selectedValues.filter((value) => value !== item.value))}
              >
                <UiIcon name="x" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div
        className={canOpen ? "project-todo-artifact-select-control" : "project-todo-artifact-select-control disabled"}
        title={selectedLabels.length > 0 ? selectedLabels.join(", ") : noSelectionLabel}
      >
        <input
          type="search"
          className="project-todo-artifact-select-input"
          role="combobox"
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          aria-label={searchLabel}
          disabled={disabled || (!canOpen && !openWhenEmpty)}
          placeholder={selectPlaceholder}
          value={searchQuery}
          onFocus={requestOpen}
          onClick={requestOpen}
          onChange={(event) => {
            setSearchQuery(event.target.value);
            requestOpen();
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              return;
            }
            if (event.key === "ArrowDown" || event.key === "Enter") {
              requestOpen();
            }
          }}
        />
        <button
          type="button"
          className="project-todo-artifact-select-toggle"
          aria-label={searchLabel}
          disabled={disabled || (!canOpen && !openWhenEmpty)}
          tabIndex={-1}
          onClick={() => {
            if (open) {
              setOpen(false);
              return;
            }
            requestOpen();
          }}
        >
          <UiIcon name="chevron-down" />
        </button>
      </div>
      {open && (
        <div id={menuId} className="project-todo-artifact-options" role="listbox" aria-label={legend} aria-multiselectable="true">
          {loading ? (
            <span className="project-todo-artifact-empty">{loadingLabel ?? emptyLabel}</span>
          ) : errorLabel !== null ? (
            <span className="project-todo-artifact-empty">{errorLabel}</span>
          ) : visibleItems.length === 0 ? (
            <span className="project-todo-artifact-empty">{emptyLabel}</span>
          ) : visibleItems.map((item) => (
            <label key={item.key} role="option" aria-selected="false">
              <input
                type="checkbox"
                disabled={disabled}
                checked={false}
                onChange={(event) => {
                  if (event.target.checked) {
                    onSelectionChange([...selectedValues, item.value]);
                    setSearchQuery("");
                  }
                }}
              />
              <span>
                <strong>{item.label}</strong>
                {item.description && <small>{item.description}</small>}
              </span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

function fallbackItem(value: string): ProjectTodoMultiSelectSearchItem {
  return {
    key: value,
    label: value,
    searchText: value.toLowerCase(),
    value
  };
}
