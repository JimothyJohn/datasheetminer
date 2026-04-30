/**
 * GitHubLink — Phase 4 of FRONTEND_TESTING.md.
 *
 * Trivial component, but the URL pin is worth a test: someone renaming the
 * repo or rebranding to a different host should see this fail before
 * shipping a stale link.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import GitHubLink from './GitHubLink';

describe('GitHubLink', () => {
  it('renders a link with the canonical repo URL', () => {
    render(<GitHubLink />);
    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe('https://github.com/JimothyJohn/specodex');
  });

  it('opens in a new tab with safe rel attributes', () => {
    render(<GitHubLink />);
    const link = screen.getByRole('link');
    expect(link.getAttribute('target')).toBe('_blank');
    const rel = link.getAttribute('rel') ?? '';
    expect(rel).toContain('noopener');
    expect(rel).toContain('noreferrer');
  });

  it('exposes an accessible label and tooltip', () => {
    render(<GitHubLink />);
    const link = screen.getByRole('link');
    expect(link.getAttribute('aria-label')).toBe('Source on GitHub');
    expect(link.getAttribute('title')).toBe('Source on GitHub');
  });
});
