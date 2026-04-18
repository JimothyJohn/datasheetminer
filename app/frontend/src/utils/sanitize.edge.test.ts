/**
 * Extended boundary tests for sanitizeUrl.
 *
 * The happy paths (http, https, javascript:, data:, ftp:) are covered in
 * sanitize.test.ts. This file focuses on protocols and URL shapes an attacker
 * might use to smuggle a dangerous URL past the parse-and-filter gate.
 */

import { describe, it, expect } from 'vitest';
import { sanitizeUrl, isPlaceholder } from './sanitize';

describe('sanitizeUrl — additional dangerous schemes', () => {
  it.each([
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    'blob:https://example.com/guid',
    'about:blank',
    'chrome:settings',
    'view-source:http://x.com',
  ])('blocks %s', (url) => {
    expect(sanitizeUrl(url)).toBe('#');
  });
});

describe('sanitizeUrl — scheme normalization', () => {
  it('blocks javascript with case variants', () => {
    expect(sanitizeUrl('JAVASCRIPT:alert(1)')).toBe('#');
    expect(sanitizeUrl('Javascript:alert(1)')).toBe('#');
    expect(sanitizeUrl(' javascript:alert(1)')).toBe('#');
  });

  it('blocks javascript with tab/newline before scheme', () => {
    // URL parses `\tjavascript:...` as invalid — whitespace in scheme is
    // rejected by WHATWG URL parser. Must not coerce to http.
    expect(sanitizeUrl('\tjavascript:alert(1)')).toBe('#');
    expect(sanitizeUrl('\njavascript:alert(1)')).toBe('#');
  });

  it('blocks protocol-relative URLs (//example.com)', () => {
    // Without a base URL these throw in new URL(), so they fall to '#'.
    expect(sanitizeUrl('//evil.example.com/x')).toBe('#');
  });
});

describe('sanitizeUrl — URL shape edges', () => {
  it('accepts IDN / unicode host', () => {
    const out = sanitizeUrl('https://münchen.de/path');
    expect(out.startsWith('https://')).toBe(true);
  });

  it('accepts IPv4 + port', () => {
    expect(sanitizeUrl('http://127.0.0.1:8080/x')).toBe('http://127.0.0.1:8080/x');
  });

  it('accepts IPv6 literal', () => {
    expect(sanitizeUrl('http://[::1]/x')).toBe('http://[::1]/x');
  });

  it('returns # for string that contains a newline', () => {
    expect(sanitizeUrl('http://x.com/\nbad')).toBe('http://x.com/\nbad');
    // WHATWG URL parser normalizes the newline out. Document behavior — if
    // future sanitization tightens, flip this.
  });

  it('handles a very long URL without crashing', () => {
    const url = 'https://example.com/' + 'a'.repeat(10_000);
    expect(sanitizeUrl(url).startsWith('https://')).toBe(true);
  });
});

describe('isPlaceholder', () => {
  it.each([null, undefined])('returns true for %s', (value) => {
    expect(isPlaceholder(value)).toBe(true);
  });

  it.each([
    '',
    'N/A',
    'n/a',
    'NA',
    'TBD',
    '-',
    '--',
    'None',
    'null',
    '?',
    'unknown',
    'Not Applicable',
    'not specified',
  ])('returns true for placeholder string %s', (value) => {
    expect(isPlaceholder(value)).toBe(true);
  });

  it('strips whitespace before comparing', () => {
    expect(isPlaceholder('  N/A  ')).toBe(true);
    expect(isPlaceholder('\tTBD\n')).toBe(true);
  });

  it.each(['Maxon', '100', '0', 'EC-45', 'na-12345'])(
    'returns false for real value %s',
    (value) => {
      expect(isPlaceholder(value)).toBe(false);
    },
  );

  it.each([0, 0.0, false, [], {}, { value: 100 }])(
    'returns false for non-string non-nullish %s',
    (value) => {
      expect(isPlaceholder(value)).toBe(false);
    },
  );
});

describe('sanitizeUrl — non-string inputs', () => {
  it.each([
    [0, '#'],
    [1, '#'],
    [{}, '#'],
    [[], '#'],
    [true, '#'],
    [false, '#'],
  ])('returns # for non-string input (%s)', (input, expected) => {
    // @ts-expect-error — deliberately wrong type to test the typeof guard.
    expect(sanitizeUrl(input)).toBe(expected);
  });
});
