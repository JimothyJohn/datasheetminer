/**
 * Tests for the AuthModal flows. Covers step transitions, form
 * submission wiring, and that errors surface without crashing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ReactNode } from 'react';
import { AuthProvider } from '../context/AuthContext';
import AuthModal from './AuthModal';

vi.mock('../api/client', () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    authLogin: vi.fn(),
    authRegister: vi.fn(),
    authConfirm: vi.fn(),
    authResendCode: vi.fn(),
    authForgotPassword: vi.fn(),
    authResetPassword: vi.fn(),
    authRefresh: vi.fn(),
  },
}));

import { apiClient } from '../api/client';

const wrap = (ui: ReactNode) => render(<AuthProvider>{ui}</AuthProvider>);

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('AuthModal — render gating', () => {
  it('renders nothing when open=false', () => {
    const { container } = wrap(<AuthModal open={false} onClose={() => {}} />);
    expect(container.querySelector('.auth-modal')).toBeNull();
  });

  it('renders the login step by default', () => {
    wrap(<AuthModal open={true} onClose={() => {}} />);
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeDefined();
    expect(screen.getByLabelText(/^email$/i)).toBeDefined();
    expect(screen.getByLabelText(/^password$/i)).toBeDefined();
  });

  it('respects initialStep', () => {
    wrap(<AuthModal open={true} initialStep="register" onClose={() => {}} />);
    expect(screen.getByRole('heading', { name: /create account/i })).toBeDefined();
  });
});

describe('AuthModal — step navigation', () => {
  it('login → forgot via Forgot password link', () => {
    wrap(<AuthModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /forgot password/i }));
    expect(screen.getByRole('heading', { name: /forgot password/i })).toBeDefined();
  });

  it('login → register via Create account link', () => {
    wrap(<AuthModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByRole('heading', { name: /create account/i })).toBeDefined();
  });

  it('register → confirm after successful submit', async () => {
    (apiClient.authRegister as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      next: 'confirm',
      message: 'check email',
    });
    wrap(<AuthModal open={true} initialStep="register" onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'CorrectHorse9Battery' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    });

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /verify email/i })).toBeDefined(),
    );
  });
});

describe('AuthModal — submit flows', () => {
  it('login: calls authLogin and closes on success', async () => {
    const exp = Math.floor(Date.now() / 1000) + 3600;
    const id = `eyJhbGciOiJSUzI1NiJ9.${btoa(JSON.stringify({ sub: 'u', email: 'a@b.co', exp })).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')}.sig`;
    (apiClient.authLogin as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id_token: id, access_token: 'a', refresh_token: 'r', expires_in: 3600,
    });

    const onClose = vi.fn();
    wrap(<AuthModal open={true} onClose={onClose} />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'pw' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    });

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(apiClient.authLogin).toHaveBeenCalledWith('a@b.co', 'pw');
  });

  it('login: surfaces error and stays open on failure', async () => {
    (apiClient.authLogin as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Invalid credentials'));

    const onClose = vi.fn();
    wrap(<AuthModal open={true} onClose={onClose} />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'wrong' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    });

    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/invalid/i));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('forgot → reset path: forgot submit advances to reset step', async () => {
    (apiClient.authForgotPassword as ReturnType<typeof vi.fn>).mockResolvedValueOnce(undefined);
    wrap(<AuthModal open={true} initialStep="forgot" onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.co' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    });

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /reset password/i })).toBeDefined(),
    );
  });

  it('confirm: success returns user to login step', async () => {
    (apiClient.authConfirm as ReturnType<typeof vi.fn>).mockResolvedValueOnce(undefined);
    wrap(<AuthModal open={true} initialStep="confirm" onClose={() => {}} />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText(/verification code/i), { target: { value: '123456' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^verify$/i }));
    });

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeDefined(),
    );
  });
});

describe('AuthModal — close behavior', () => {
  it('Escape key triggers onClose', () => {
    const onClose = vi.fn();
    wrap(<AuthModal open={true} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('clicking the × button triggers onClose', () => {
    const onClose = vi.fn();
    wrap(<AuthModal open={true} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText(/close/i));
    expect(onClose).toHaveBeenCalled();
  });
});
