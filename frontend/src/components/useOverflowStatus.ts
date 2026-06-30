import { useCallback, useLayoutEffect, useState, type RefCallback } from "react";

export function useOverflowStatus<T extends HTMLElement>(): [RefCallback<T>, boolean] {
  const [node, setNode] = useState<T | null>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  const ref = useCallback((node: T | null) => {
    setNode(node);
  }, []);

  useLayoutEffect(() => {
    if (node === null) {
      setIsOverflowing(false);
      return;
    }

    const measure = () => {
      setIsOverflowing(node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight);
    };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(node);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [node]);

  return [ref, isOverflowing];
}
