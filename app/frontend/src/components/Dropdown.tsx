import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';

export interface DropdownOption<V extends string | number = string> {
  value: V;
  label: string;
  disabled?: boolean;
}

interface DropdownProps<V extends string | number = string> {
  value: V;
  options: DropdownOption<V>[];
  onChange: (value: V) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  ariaLabel?: string;
  id?: string;
  name?: string;
  fullWidth?: boolean;
}

interface PopoverRect {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
  placement: 'below' | 'above';
}

const POPOVER_GAP = 4;
const POPOVER_PAD = 8;

export default function Dropdown<V extends string | number = string>({
  value,
  options,
  onChange,
  placeholder = 'Select...',
  disabled = false,
  className,
  ariaLabel,
  id,
  name,
  fullWidth = false,
}: DropdownProps<V>) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [rect, setRect] = useState<PopoverRect | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const reactId = useId();
  const listboxId = id ? `${id}-listbox` : `dropdown-${reactId}-listbox`;

  const selectedIndex = useMemo(
    () => options.findIndex((opt) => opt.value === value),
    [options, value],
  );

  const selectedLabel = selectedIndex >= 0 ? options[selectedIndex].label : '';

  const computeRect = useCallback((): PopoverRect | null => {
    const trigger = triggerRef.current;
    if (!trigger) return null;
    const tRect = trigger.getBoundingClientRect();
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - tRect.bottom - POPOVER_PAD;
    const spaceAbove = tRect.top - POPOVER_PAD;
    const placeAbove = spaceBelow < 180 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(120, Math.min(320, placeAbove ? spaceAbove : spaceBelow));
    return {
      top: placeAbove ? tRect.top - POPOVER_GAP : tRect.bottom + POPOVER_GAP,
      left: tRect.left,
      width: tRect.width,
      maxHeight,
      placement: placeAbove ? 'above' : 'below',
    };
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    setRect(computeRect());
    const handler = () => setRect(computeRect());
    window.addEventListener('resize', handler);
    window.addEventListener('scroll', handler, true);
    return () => {
      window.removeEventListener('resize', handler);
      window.removeEventListener('scroll', handler, true);
    };
  }, [open, computeRect]);

  useEffect(() => {
    if (!open) return;
    const handlePointer = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        triggerRef.current?.contains(target) ||
        listRef.current?.contains(target)
      ) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener('mousedown', handlePointer);
    return () => document.removeEventListener('mousedown', handlePointer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const initial = selectedIndex >= 0 ? selectedIndex : 0;
    setActiveIndex(Math.min(initial, options.length - 1));
  }, [open, selectedIndex, options.length]);

  // Scroll the active item into view as the user navigates.
  useEffect(() => {
    if (!open || activeIndex < 0) return;
    const list = listRef.current;
    if (!list) return;
    const item = list.children[activeIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex, open]);

  const moveActive = (delta: number) => {
    const n = options.length;
    if (n === 0) return;
    setActiveIndex((prev) => {
      let next = prev;
      for (let i = 0; i < n; i++) {
        next = (next + delta + n) % n;
        if (!options[next].disabled) return next;
      }
      return prev;
    });
  };

  const commit = (idx: number) => {
    const opt = options[idx];
    if (!opt || opt.disabled) return;
    onChange(opt.value);
    setOpen(false);
    triggerRef.current?.focus();
  };

  // The trigger keeps focus while open; popover navigation is driven from
  // the trigger via aria-activedescendant rather than focusing the listbox,
  // since shifting focus into a portaled list interacts badly with
  // overlay/modal containers.
  const handleTriggerKey = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) setOpen(true);
      else moveActive(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) setOpen(true);
      else moveActive(-1);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!open) setOpen(true);
      else commit(activeIndex);
    } else if (e.key === 'Home' && open) {
      e.preventDefault();
      const first = options.findIndex((o) => !o.disabled);
      if (first >= 0) setActiveIndex(first);
    } else if (e.key === 'End' && open) {
      e.preventDefault();
      for (let i = options.length - 1; i >= 0; i--) {
        if (!options[i].disabled) {
          setActiveIndex(i);
          break;
        }
      }
    } else if (e.key === 'Escape' && open) {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === 'Tab' && open) {
      setOpen(false);
    }
  };

  const triggerClass = ['custom-dropdown-trigger', className, fullWidth ? 'custom-dropdown-trigger--full' : '']
    .filter(Boolean)
    .join(' ');

  const labelDisplay = selectedLabel || placeholder;
  const activeOptionId =
    open && activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        id={id}
        name={name}
        className={triggerClass}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={activeOptionId}
        aria-label={ariaLabel}
        disabled={disabled}
        data-placeholder={selectedLabel ? undefined : 'true'}
        data-open={open ? 'true' : undefined}
        onClick={() => !disabled && setOpen((v) => !v)}
        onKeyDown={handleTriggerKey}
      >
        <span className="custom-dropdown-trigger-label">{labelDisplay}</span>
        <span className="custom-dropdown-trigger-caret" aria-hidden="true">▾</span>
      </button>
      {open && rect &&
        createPortal(
          <ul
            ref={listRef}
            id={listboxId}
            role="listbox"
            tabIndex={-1}
            className="custom-dropdown-list"
            data-placement={rect.placement}
            style={{
              position: 'fixed',
              top: rect.placement === 'above' ? undefined : rect.top,
              bottom: rect.placement === 'above' ? window.innerHeight - rect.top : undefined,
              left: rect.left,
              width: rect.width,
              maxHeight: rect.maxHeight,
            }}
          >
            {options.length === 0 && (
              <li className="custom-dropdown-empty" role="presentation">
                No options
              </li>
            )}
            {options.map((opt, idx) => {
              const isSelected = idx === selectedIndex;
              const isActive = idx === activeIndex;
              const cls = [
                'custom-dropdown-item',
                isSelected ? 'custom-dropdown-item--selected' : '',
                isActive ? 'custom-dropdown-item--active' : '',
                opt.disabled ? 'custom-dropdown-item--disabled' : '',
              ]
                .filter(Boolean)
                .join(' ');
              return (
                <li
                  key={`${String(opt.value)}-${idx}`}
                  id={`${listboxId}-opt-${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={opt.disabled || undefined}
                  className={cls}
                  onMouseEnter={() => !opt.disabled && setActiveIndex(idx)}
                  onMouseDown={(e) => {
                    // Prevent focus shift before click handler fires.
                    e.preventDefault();
                  }}
                  onClick={() => commit(idx)}
                >
                  {opt.label}
                </li>
              );
            })}
          </ul>,
          document.body,
        )}
    </>
  );
}
