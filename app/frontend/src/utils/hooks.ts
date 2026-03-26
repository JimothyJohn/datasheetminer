/**
 * Custom React Hooks: Performance & utility hooks
 *
 * Provides reusable hooks for common patterns like debouncing, throttling,
 * and memoization to improve application performance.
 *
 * @module hooks
 */

import { useEffect, useState, useRef, useCallback } from 'react';

/**
 * useDebounce hook
 *
 * Delays updating a value until after a specified delay has passed since
 * the last change. Useful for expensive operations like API calls or filtering.
 *
 * Use Cases:
 * - Search input filtering (wait for user to stop typing)
 * - Filter value updates (reduce re-renders)
 * - Auto-save functionality (wait for user to pause editing)
 *
 * Performance Impact:
 * - Reduces function calls by ~90% for rapid updates
 * - Example: 100 keystrokes → 1 debounced update (with 300ms delay)
 *
 * @param value - Value to debounce
 * @param delay - Delay in milliseconds (default: 300ms)
 * @returns Debounced value that updates after delay
 *
 * @example
 * ```typescript
 * function SearchInput() {
 *   const [search, setSearch] = useState('');
 *   const debouncedSearch = useDebounce(search, 300);
 *
 *   // debouncedSearch only updates 300ms after user stops typing
 *   useEffect(() => {
 *     performExpensiveSearch(debouncedSearch);
 *   }, [debouncedSearch]);
 *
 *   return <input value={search} onChange={(e) => setSearch(e.target.value)} />;
 * }
 * ```
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // Set up timeout to update debounced value after delay
    const timeoutId = setTimeout(() => {
      console.log(`[useDebounce] Updating debounced value after ${delay}ms`);
      setDebouncedValue(value);
    }, delay);

    // Cleanup: cancel timeout if value changes before delay elapses
    return () => {
      clearTimeout(timeoutId);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * useThrottle hook
 *
 * Ensures a value only updates at most once per specified interval.
 * Unlike debounce (which waits for silence), throttle ensures regular updates.
 *
 * Use Cases:
 * - Scroll event handlers (limit re-renders during scrolling)
 * - Resize event handlers (limit expensive layout calculations)
 * - Real-time data updates (limit update frequency)
 *
 * Performance Impact:
 * - Guarantees maximum update frequency
 * - Example: 100 scroll events → 10 throttled updates (with 100ms interval)
 *
 * @param value - Value to throttle
 * @param interval - Minimum time between updates in milliseconds (default: 100ms)
 * @returns Throttled value that updates at most once per interval
 *
 * @example
 * ```typescript
 * function ScrollTracker() {
 *   const [scrollY, setScrollY] = useState(0);
 *   const throttledScrollY = useThrottle(scrollY, 100);
 *
 *   useEffect(() => {
 *     const handleScroll = () => setScrollY(window.scrollY);
 *     window.addEventListener('scroll', handleScroll);
 *     return () => window.removeEventListener('scroll', handleScroll);
 *   }, []);
 *
 *   // Expensive operation only runs every 100ms max
 *   useEffect(() => {
 *     updateScrollIndicator(throttledScrollY);
 *   }, [throttledScrollY]);
 * }
 * ```
 */
export function useThrottle<T>(value: T, interval: number = 100): T {
  const [throttledValue, setThrottledValue] = useState<T>(value);
  const lastUpdated = useRef<number>(Date.now());

  useEffect(() => {
    const now = Date.now();
    const timeSinceLastUpdate = now - lastUpdated.current;

    if (timeSinceLastUpdate >= interval) {
      // Enough time has passed, update immediately
      console.log(`[useThrottle] Updating throttled value (${timeSinceLastUpdate}ms since last update)`);
      setThrottledValue(value);
      lastUpdated.current = now;
    } else {
      // Schedule update for when interval elapses
      const timeoutId = setTimeout(() => {
        console.log(`[useThrottle] Updating throttled value after timeout`);
        setThrottledValue(value);
        lastUpdated.current = Date.now();
      }, interval - timeSinceLastUpdate);

      return () => clearTimeout(timeoutId);
    }
  }, [value, interval]);

  return throttledValue;
}

/**
 * usePrevious hook
 *
 * Returns the previous value of a variable from the last render.
 * Useful for comparing current vs previous values in effects.
 *
 * Use Cases:
 * - Detecting value changes (compare current vs previous)
 * - Conditional effects (only run when value actually changed)
 * - Animations (animate from previous to current value)
 *
 * @param value - Value to track
 * @returns Previous value (undefined on first render)
 *
 * @example
 * ```typescript
 * function Counter({ count }: { count: number }) {
 *   const prevCount = usePrevious(count);
 *
 *   useEffect(() => {
 *     if (prevCount !== undefined && count !== prevCount) {
 *       console.log(`Count changed from ${prevCount} to ${count}`);
 *     }
 *   }, [count, prevCount]);
 * }
 * ```
 */
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref.current;
}

/**
 * useIsMounted hook
 *
 * Returns a function that returns true if component is still mounted.
 * Useful for preventing state updates on unmounted components.
 *
 * Use Cases:
 * - Async operations (check if component still mounted before setState)
 * - Cleanup prevention (avoid memory leaks)
 * - Conditional updates (only update if component active)
 *
 * @returns Function that returns true if component is mounted
 *
 * @example
 * ```typescript
 * function DataLoader() {
 *   const [data, setData] = useState(null);
 *   const isMounted = useIsMounted();
 *
 *   useEffect(() => {
 *     fetchData().then(result => {
 *       // Only update state if component still mounted
 *       if (isMounted()) {
 *         setData(result);
 *       }
 *     });
 *   }, []);
 * }
 * ```
 */
export function useIsMounted(): () => boolean {
  const isMountedRef = useRef(true);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return useCallback(() => isMountedRef.current, []);
}

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
