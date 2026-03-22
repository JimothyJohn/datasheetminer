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
