/**
 * Sanitize a URL to prevent XSS via javascript: or data: protocols.
 * Only allows http and https URLs. Returns '#' for anything else.
 */
export function sanitizeUrl(url: string | undefined | null): string {
  if (!url || typeof url !== 'string') return '#';
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return url;
    }
    return '#';
  } catch {
    return '#';
  }
}

// Mirrors specodex/placeholders.py::PLACEHOLDER_STRINGS. The backend
// coerces these to null at ingest, but older rows in prod still carry literal
// "N/A"s, so the frontend has to stay defensive until the backfill completes.
const PLACEHOLDER_STRINGS = new Set([
  '',
  'n/a',
  'na',
  'tbd',
  'tba',
  '-',
  '--',
  'none',
  'null',
  '?',
  'unknown',
  'not available',
  'not applicable',
  'not specified',
]);

/**
 * True when a field value is effectively missing — either null/undefined or
 * a known placeholder string ("N/A", "TBD", etc.). Use anywhere a cell's
 * default rendering would otherwise surface literal "N/A" to the user.
 */
export function isPlaceholder(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') {
    return PLACEHOLDER_STRINGS.has(value.trim().toLowerCase());
  }
  return false;
}
