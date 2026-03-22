/**
 * Tests for NetworkStatus component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import NetworkStatus from './NetworkStatus';

describe('NetworkStatus', () => {
  let originalOnLine: boolean;

  beforeEach(() => {
    originalOnLine = navigator.onLine;
  });

  it('renders nothing when online', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true });
    const { container } = render(<NetworkStatus />);
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('shows banner when offline', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true });
    render(<NetworkStatus />);
    expect(screen.getByRole('alert')).toBeDefined();
    expect(screen.getByText('No internet connection.')).toBeDefined();
  });

  it('shows banner when connection is lost', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true });
    render(<NetworkStatus />);

    // Simulate going offline
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: false, writable: true });
      window.dispatchEvent(new Event('offline'));
    });

    expect(screen.getByRole('alert')).toBeDefined();
  });

  it('hides banner when connection is restored', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true });
    const { container } = render(<NetworkStatus />);

    // Verify banner is showing
    expect(screen.getByRole('alert')).toBeDefined();

    // Simulate coming back online
    act(() => {
      Object.defineProperty(navigator, 'onLine', { value: true, writable: true });
      window.dispatchEvent(new Event('online'));
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('has assertive aria-live attribute', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true });
    render(<NetworkStatus />);
    const alert = screen.getByRole('alert');
    expect(alert.getAttribute('aria-live')).toBe('assertive');
  });
});
