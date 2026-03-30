/**
 * Custom React Hooks
 *
 * @module hooks
 */

import { useEffect, useState, useRef, useCallback } from 'react';

/**
 * useColumnResize hook
 *
 * Enables drag-to-resize on table columns. Returns column widths and a
 * mousedown handler to attach to resize handles in each header cell.
 *
 * @param initialWidths - Map of column key → initial pixel width
 * @returns columnWidths state, setter, and startResize handler
 */
export function useColumnResize(initialWidths: Record<string, number>) {
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(initialWidths);
  const resizeState = useRef<{ key: string; startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!resizeState.current) return;
      const delta = e.clientX - resizeState.current.startX;
      const newWidth = Math.max(40, resizeState.current.startWidth + delta);
      setColumnWidths(prev => ({ ...prev, [resizeState.current!.key]: newWidth }));
    };

    const onMouseUp = () => {
      if (!resizeState.current) return;
      resizeState.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const startResize = useCallback((key: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    resizeState.current = {
      key,
      startX: e.clientX,
      startWidth: columnWidths[key] ?? 70,
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [columnWidths]);

  return { columnWidths, setColumnWidths, startResize };
}
