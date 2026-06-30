import { useEffect, useRef } from "react";

export type ProjectTodoDispatchToastState = {
  id: number;
  message: string;
  tone: "success" | "error";
};

type ProjectTodoDispatchToastProps = {
  toast: ProjectTodoDispatchToastState | null;
  onDismiss: (id: number) => void;
};

export function ProjectTodoDispatchToast({ toast, onDismiss }: ProjectTodoDispatchToastProps) {
  const onDismissRef = useRef(onDismiss);

  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    if (toast === null) {
      return;
    }
    const timeout = window.setTimeout(() => onDismissRef.current(toast.id), 2000);
    return () => window.clearTimeout(timeout);
  }, [toast?.id]);

  if (toast === null) {
    return null;
  }

  return (
    <div
      className={`project-todo-dispatch-toast ${toast.tone}`}
      role="status"
      aria-live="polite"
    >
      {toast.message}
    </div>
  );
}
