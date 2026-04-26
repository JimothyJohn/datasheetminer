/**
 * Sticky bottom-of-viewport tray showing the in-progress motion-system build.
 *
 * Three slots — drive, motor, gearhead. Filled slots show the chosen product
 * with a remove affordance. Empty slots are inert; the user fills them by
 * picking the type in the sidebar dropdown and clicking "Add to build" inside
 * a product's detail modal.
 *
 * Junction badges between filled adjacent slots run the same client-side
 * compat check used by the list filter — strict-failed junctions show as
 * partial here too (fits-partial mode), but the colour cue still points at
 * which junction to inspect.
 */
import { useApp } from '../context/AppContext';
import { BUILD_SLOTS, BuildSlot, check } from '../utils/compat';
import CompatBadge from './CompatBadge';

const SLOT_LABEL: Record<BuildSlot, string> = {
  drive: 'Drive',
  motor: 'Motor',
  gearhead: 'Gearhead',
};

export default function BuildTray() {
  const { build, removeFromBuild, clearBuild } = useApp();
  const filledCount = Object.values(build).filter(Boolean).length;
  if (filledCount === 0) return null;

  return (
    <div className="build-tray" role="region" aria-label="Motion system build">
      <div className="build-tray-inner">
        <span className="build-tray-label">Build:</span>
        {BUILD_SLOTS.map((slot, idx) => {
          const product = build[slot];
          const isLast = idx === BUILD_SLOTS.length - 1;
          // Junction between this slot and the next, when both are filled.
          const next = BUILD_SLOTS[idx + 1];
          const nextProduct = next ? build[next] : undefined;
          let junctionStatus: 'ok' | 'partial' | null = null;
          let junctionDetail = '';
          if (product && nextProduct) {
            try {
              const r = check(product, nextProduct);
              // Soften fail→partial for display.
              junctionStatus = r.status === 'fail' ? 'partial' : r.status;
              if (r.status !== 'ok') {
                const issues = r.results.flatMap(p => p.checks.filter(c => c.status !== 'ok'));
                junctionDetail = issues.map(c => `${c.field}: ${c.detail}`).join(' • ') || 'partial match';
              }
            } catch {
              junctionStatus = null;
            }
          }
          return (
            <span key={slot} className="build-tray-slot-wrap">
              <span className={`build-tray-slot ${product ? 'filled' : 'empty'}`}>
                <span className="build-tray-slot-type">{SLOT_LABEL[slot]}</span>
                {product ? (
                  <>
                    <span className="build-tray-slot-name">
                      {product.manufacturer || 'Unknown'}
                      {product.part_number ? ` — ${product.part_number}` : ''}
                    </span>
                    <button
                      type="button"
                      className="build-tray-remove"
                      onClick={() => removeFromBuild(slot)}
                      aria-label={`Remove ${SLOT_LABEL[slot]} from build`}
                      title="Remove"
                    >
                      ×
                    </button>
                  </>
                ) : (
                  <span className="build-tray-slot-empty">empty</span>
                )}
              </span>
              {!isLast && (
                <span className="build-tray-junction">
                  {junctionStatus ? (
                    <CompatBadge status={junctionStatus} detail={junctionDetail || undefined} />
                  ) : (
                    <span className="build-tray-arrow" aria-hidden="true">→</span>
                  )}
                </span>
              )}
            </span>
          );
        })}
        <button type="button" className="build-tray-clear" onClick={clearBuild}>
          Clear
        </button>
      </div>
    </div>
  );
}
