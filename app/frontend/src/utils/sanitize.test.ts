import { describe, it, expect } from 'vitest';
import { sanitizeUrl } from './sanitize';

describe('sanitizeUrl', () => {
  it('allows http URLs', () => {
    expect(sanitizeUrl('http://example.com/datasheet.pdf')).toBe('http://example.com/datasheet.pdf');
  });

  it('allows https URLs', () => {
    expect(sanitizeUrl('https://example.com/datasheet.pdf')).toBe('https://example.com/datasheet.pdf');
  });

  it('blocks javascript: protocol', () => {
    expect(sanitizeUrl('javascript:alert(1)')).toBe('#');
  });

  it('blocks data: protocol', () => {
    expect(sanitizeUrl('data:text/html,<script>alert(1)</script>')).toBe('#');
  });

  it('blocks ftp: protocol', () => {
    expect(sanitizeUrl('ftp://example.com/file')).toBe('#');
  });

  it('returns # for empty string', () => {
    expect(sanitizeUrl('')).toBe('#');
  });

  it('returns # for null', () => {
    expect(sanitizeUrl(null)).toBe('#');
  });

  it('returns # for undefined', () => {
    expect(sanitizeUrl(undefined)).toBe('#');
  });

  it('returns # for malformed URL', () => {
    expect(sanitizeUrl('not-a-url')).toBe('#');
  });
});
