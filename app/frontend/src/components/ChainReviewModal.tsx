/**
 * Chain review modal — opens from BuildTray when ≥2 adjacent slots are
 * filled. Stacks one CompatibilityReport per adjacent filled pair so the
 * user can audit the whole BOM without reopening each product detail.
 *
 * Uses the same `apiClient.checkCompat` POST that CompatChecker uses,
 * one call per pair, fired in parallel on open. Render shape mirrors
 * CompatChecker so a user who's already seen the per-product checker
 * isn't reading a new layout.
 */
import { useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';
import { useApp } from '../context/AppContext';
import { Product } from '../types/models';
import { CompatibilityReport } from '../types/compat';
import { BUILD_SLOTS, BuildSlot } from '../utils/compat';
import CompatBadge from './CompatBadge';

const SLOT_LABEL: Record<BuildSlot, string> = {
  drive: 'Drive',
  motor: 'Motor',
  gearhead: 'Gearhead',
};

interface ChainReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface PairResult {
  from: BuildSlot;
  to: BuildSlot;
  fromProduct: Product;
  toProduct: Product;
  status: 'idle' | 'loading' | 'ready' | 'error';
  report?: CompatibilityReport;
  error?: string;
}

/** Build the list of adjacent filled pairs in BUILD_SLOTS order. */
export function adjacentFilledPairs(
  build: Partial<Record<BuildSlot, Product>>,
): Array<{ from: BuildSlot; to: BuildSlot; a: Product; b: Product }> {
  const out: Array<{ from: BuildSlot; to: BuildSlot; a: Product; b: Product }> = [];
  for (let i = 0; i < BUILD_SLOTS.length - 1; i++) {
    const from = BUILD_SLOTS[i];
    const to = BUILD_SLOTS[i + 1];
    const a = build[from];
    const b = build[to];
    if (a && b) out.push({ from, to, a, b });
  }
  return out;
}

function productLabel(p: Product): string {
  const part = p.part_number ? ` — ${p.part_number}` : '';
  return `${p.manufacturer || 'Unknown'}${part}`;
}

export default function ChainReviewModal({ isOpen, onClose }: ChainReviewModalProps) {
  const { build } = useApp();
  const modalRef = useRef<HTMLDivElement>(null);
  const [pairs, setPairs] = useState<PairResult[]>([]);

  // Escape + click-outside close, mirroring ProductDetailModal.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const onMouse = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onMouse);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onMouse);
    };
  }, [isOpen, onClose]);

  // Load every adjacent-filled-pair report in parallel on open. Re-runs
  // when the build changes so re-opening picks up the latest state.
  useEffect(() => {
    if (!isOpen) return;
    const initial: PairResult[] = adjacentFilledPairs(build).map(p => ({
      from: p.from,
      to: p.to,
      fromProduct: p.a,
      toProduct: p.b,
      status: 'loading',
    }));
    setPairs(initial);
    if (initial.length === 0) return;

    let cancelled = false;
    Promise.all(
      initial.map(async (p, idx) => {
        try {
          const report = await apiClient.checkCompat(
            { id: p.fromProduct.product_id, type: p.from },
            { id: p.toProduct.product_id, type: p.to },
          );
          return { idx, status: 'ready' as const, report };
        } catch (err) {
          return {
            idx,
            status: 'error' as const,
            error: err instanceof Error ? err.message : 'Compatibility check failed',
          };
        }
      }),
    ).then(results => {
      if (cancelled) return;
      setPairs(prev =>
        prev.map((p, i) => {
          const r = results.find(x => x.idx === i);
          if (!r) return p;
          return r.status === 'ready'
            ? { ...p, status: 'ready', report: r.report }
            : { ...p, status: 'error', error: r.error };
        }),
      );
    });

    return () => {
      cancelled = true;
    };
  }, [isOpen, build]);

  if (!isOpen) return null;

  return (
    <div className="chain-review-overlay" role="dialog" aria-modal="true" aria-label="Chain review">
      <div ref={modalRef} className="chain-review-modal">
        <div className="chain-review-header">
          <h2 className="chain-review-title">Chain review</h2>
          <button
            type="button"
            className="chain-review-close"
            onClick={onClose}
            aria-label="Close chain review"
          >
            ×
          </button>
        </div>

        {pairs.length === 0 && (
          <p className="chain-review-empty">
            Add at least two adjacent products (drive + motor, or motor + gearhead) to review the chain.
          </p>
        )}

        {pairs.map(p => (
          <section key={`${p.from}-${p.to}`} className="chain-review-pair">
            <div className="chain-review-pair-header">
              <span className="chain-review-pair-title">
                {SLOT_LABEL[p.from]} → {SLOT_LABEL[p.to]}
              </span>
              {p.status === 'ready' && p.report && <CompatBadge status={p.report.status} />}
            </div>
            <div className="chain-review-pair-products">
              <span>{productLabel(p.fromProduct)}</span>
              <span aria-hidden="true">→</span>
              <span>{productLabel(p.toProduct)}</span>
            </div>

            {p.status === 'loading' && <p className="compat-hint">Running compatibility check…</p>}
            {p.status === 'error' && <p className="compat-error">{p.error}</p>}
            {p.status === 'ready' && p.report && p.report.results.length === 0 && (
              <p className="compat-hint">No comparator results returned.</p>
            )}
            {p.status === 'ready' && p.report && p.report.results.length > 0 && p.report.results.map(pair => (
              <div key={`${pair.from_port}|${pair.to_port}`} className="compat-junction">
                <div className="compat-junction-header">
                  <CompatBadge status={pair.status} />
                  <span className="compat-junction-title">
                    {pair.from_port} → {pair.to_port}
                  </span>
                </div>
                <table className="spec-table">
                  <tbody>
                    {pair.checks.map(c => (
                      <tr key={c.field} className="spec-row">
                        <td className="spec-label">{c.field}</td>
                        <td className="spec-value">{c.detail}</td>
                        <td className="spec-unit">
                          <CompatBadge status={c.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
