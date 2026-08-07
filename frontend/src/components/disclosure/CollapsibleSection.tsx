import { forwardRef, useEffect, useImperativeHandle, useRef, type ReactNode } from "react";

/**
 * Native <details>/<summary> disclosure, styled to match the app's existing
 * "view as table" collapsible idiom (see .chart-data-table in global.css).
 * Used for advanced/expert content that should stay reachable but not
 * compete with the primary content by default.
 *
 * The `open` attribute is deliberately never passed as a React prop —
 * React would then "control" it and snap it back to `defaultOpen` on the
 * next re-render, fighting both the browser's native toggle and any caller
 * that opens the section imperatively via the forwarded ref (e.g. a backend
 * validation error landing on a field inside a collapsed section — closed
 * <details> content isn't focusable, so it must be opened first). Instead,
 * `defaultOpen` is applied once, imperatively, on mount.
 */
export const CollapsibleSection = forwardRef<
  HTMLDetailsElement,
  { title: string; defaultOpen?: boolean; children: ReactNode }
>(function CollapsibleSection({ title, defaultOpen = false, children }, forwardedRef) {
  const detailsRef = useRef<HTMLDetailsElement | null>(null);
  useImperativeHandle(forwardedRef, () => detailsRef.current as HTMLDetailsElement, []);

  useEffect(() => {
    if (detailsRef.current) {
      detailsRef.current.open = defaultOpen;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <details ref={detailsRef} className="collapsible-section">
      <summary className="collapsible-section__summary">{title}</summary>
      <div className="collapsible-section__body">{children}</div>
    </details>
  );
});
