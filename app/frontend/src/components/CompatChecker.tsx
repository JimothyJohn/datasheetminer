/**
 * "Check against another product" panel inside ProductDetailModal.
 *
 * Given the currently-open product, pick a candidate from one of the
 * adjacent product types (drive↔motor, motor↔gearhead) and POST to the
 * compat engine. Renders junctions with side-by-side field detail and
 * status badges. Fits-partial only — nothing here gates selection.
 *
 * If the user has a build anchor of an adjacent type, that anchor is
 * pre-selected and pinned to the top of the candidate list, so opening
 * any motor with a drive in the build immediately shows how it would
 * mate with that drive.
 */
import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../api/client';
import { useApp } from '../context/AppContext';
import { Product } from '../types/models';
import { CompatibilityReport } from '../types/compat';
import { ADJACENT_TYPES, BuildSlot } from '../utils/compat';
import CompatBadge from './CompatBadge';

type Adjacent = 'drive' | 'motor' | 'gearhead';

interface CompatCheckerProps {
  product: Product;
}

function productLabel(p: Product): string {
  const part = p.part_number ? ` — ${p.part_number}` : '';
  return `${p.manufacturer || 'Unknown'}${part}`;
}

export default function CompatChecker({ product }: CompatCheckerProps) {
  const { products: cached, build } = useApp();
  const adjacentTypes = (ADJACENT_TYPES[product.product_type] ?? []) as Adjacent[];

  // Prefer an adjacent type that has a build anchor — opening a motor with a
  // drive in the build should default to "vs drive" without making the user
  // click a tab.
  const initialType: Adjacent | null = useMemo(() => {
    const anchored = adjacentTypes.find(t => build[t as BuildSlot]);
    return anchored ?? adjacentTypes[0] ?? null;
  }, [adjacentTypes, build]);

  const [activeType, setActiveType] = useState<Adjacent | null>(initialType);
  const [candidates, setCandidates] = useState<Product[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  // The build anchor for the currently active adjacent type, if any.
  const anchor = activeType ? build[activeType as BuildSlot] : undefined;

  // Load candidates for the active type. Reuses the AppContext products
  // cache when it already has the right type loaded; otherwise hits the API.
  // Always prepends the build anchor (if any) so the user can pick it even
  // when it's not in the cached list.
  useEffect(() => {
    if (!activeType) return;
    setReportError(null);
    setQuery('');
    // Pre-select the build anchor on every type switch so the report renders
    // immediately. The user can pick another candidate from the list.
    setSelectedId(anchor?.product_id ?? null);

    const fromCache = cached.filter(p => p.product_type === activeType);
    if (fromCache.length > 0) {
      setCandidates(fromCache);
      return;
    }
    setLoadingCandidates(true);
    apiClient
      .listProducts(activeType, 100)
      .then(rows => setCandidates(rows.filter(p => p.product_type === activeType)))
      .catch(() => setCandidates([]))
      .finally(() => setLoadingCandidates(false));
  }, [activeType, cached, anchor?.product_id]);

  // Build the visible list: dedupe the anchor (if it's also in `candidates`),
  // then pin it to the top, then apply the search filter, then cap at 50.
  const visible = useMemo(() => {
    const seen = new Set<string>();
    const ordered: Product[] = [];
    if (anchor) {
      ordered.push(anchor);
      seen.add(anchor.product_id);
    }
    for (const p of candidates) {
      if (!seen.has(p.product_id)) {
        ordered.push(p);
        seen.add(p.product_id);
      }
    }
    if (!query.trim()) return ordered.slice(0, 50);
    const q = query.trim().toLowerCase();
    return ordered.filter(p => productLabel(p).toLowerCase().includes(q)).slice(0, 50);
  }, [candidates, query, anchor]);

  // Run the check when a candidate is selected.
  useEffect(() => {
    if (!selectedId || !activeType) return;
    const candidate =
      anchor && anchor.product_id === selectedId
        ? anchor
        : candidates.find(p => p.product_id === selectedId);
    if (!candidate) return;

    setReportLoading(true);
    setReport(null);
    setReportError(null);
    apiClient
      .checkCompat(
        { id: product.product_id, type: product.product_type as Adjacent },
        { id: candidate.product_id, type: activeType },
      )
      .then(setReport)
      .catch(err => setReportError(err instanceof Error ? err.message : 'Compatibility check failed'))
      .finally(() => setReportLoading(false));
  }, [selectedId, activeType, candidates, anchor, product]);

  if (adjacentTypes.length === 0) return null;

  const headerText = anchor ? 'Check against your build' : 'Check compatibility';

  return (
    <div className="compat-checker">
      <div className="compat-checker-header">
        <h3 className="spec-category-title">{headerText}</h3>
        {adjacentTypes.length > 1 && (
          <div className="compat-type-tabs">
            {adjacentTypes.map(t => (
              <button
                key={t}
                type="button"
                className={`compat-type-tab ${activeType === t ? 'active' : ''}`}
                onClick={() => setActiveType(t)}
              >
                vs {t}
                {build[t as BuildSlot] && <span className="compat-type-tab-dot" aria-hidden="true">•</span>}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="compat-picker">
        <input
          type="text"
          className="compat-search"
          placeholder={`Search ${activeType ?? ''}s by manufacturer or part number…`}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        {loadingCandidates && <p className="compat-hint">Loading {activeType}s…</p>}
        {!loadingCandidates && visible.length === 0 && (
          <p className="compat-hint">No {activeType}s available.</p>
        )}
        {!loadingCandidates && visible.length > 0 && (
          <ul className="compat-candidate-list">
            {visible.map(p => {
              const isAnchor = anchor?.product_id === p.product_id;
              return (
                <li key={p.product_id}>
                  <button
                    type="button"
                    className={`compat-candidate ${selectedId === p.product_id ? 'active' : ''}`}
                    onClick={() => setSelectedId(p.product_id)}
                  >
                    {isAnchor && <span className="compat-candidate-tag">In build</span>}
                    {productLabel(p)}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="compat-report">
        {reportLoading && <p className="compat-hint">Running compatibility check…</p>}
        {reportError && <p className="compat-error">{reportError}</p>}
        {report && (
          <>
            <div className="compat-overall">
              <CompatBadge status={report.status} />
              <span className="compat-overall-text">
                {report.from_type} → {report.to_type}
              </span>
            </div>
            {report.results.map(pair => (
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
          </>
        )}
      </div>
    </div>
  );
}
