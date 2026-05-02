/**
 * Tests for the "Add to project" menu — disabled CTA when logged out,
 * checkbox toggle wiring, inline create flow, error display.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ReactNode } from 'react';
import AddToProjectMenu from './AddToProjectMenu';
import type { Project, ProductRef } from '../types/projects';

const mockListProjects = vi.fn();
const mockCreateProject = vi.fn();
const mockAddProductToProject = vi.fn();
const mockRemoveProductFromProject = vi.fn();

vi.mock('../api/client', () => ({
  apiClient: {
    setAuthToken: vi.fn(),
    listProjects: (...args: unknown[]) => mockListProjects(...args),
    createProject: (...args: unknown[]) => mockCreateProject(...args),
    addProductToProject: (...args: unknown[]) => mockAddProductToProject(...args),
    removeProductFromProject: (...args: unknown[]) => mockRemoveProductFromProject(...args),
  },
}));

const mockUseAuth = vi.fn();
vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

import { ProjectsProvider } from '../context/ProjectsContext';

const REF: ProductRef = { product_type: 'motor', product_id: 'm-1' };

function project(over: Partial<Project> = {}): Project {
  const now = new Date().toISOString();
  return {
    id: 'p1',
    name: 'Cell A',
    owner_sub: 'sub-1',
    product_refs: [],
    created_at: now,
    updated_at: now,
    ...over,
  };
}

const wrap = (ui: ReactNode) => render(<ProjectsProvider>{ui}</ProjectsProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  mockListProjects.mockResolvedValue([]);
});

describe('logged out', () => {
  it('shows the sign-in CTA and no trigger button', () => {
    mockUseAuth.mockReturnValue({ user: null });
    wrap(<AddToProjectMenu productRef={REF} />);
    expect(screen.getByText(/sign in to save/i)).toBeDefined();
    expect(screen.queryByRole('button', { name: /add to project/i })).toBeNull();
  });

  it('does not call listProjects when logged out', () => {
    mockUseAuth.mockReturnValue({ user: null });
    wrap(<AddToProjectMenu productRef={REF} />);
    expect(mockListProjects).not.toHaveBeenCalled();
  });
});

describe('logged in — popover', () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user: { sub: 'sub-1', email: 'a@b.co', groups: [] } });
  });

  it('fetches projects on mount and opens the popover with them', async () => {
    mockListProjects.mockResolvedValueOnce([project({ id: 'p1', name: 'Robot' })]);

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText('Robot')).toBeDefined());
  });

  it('shows an empty-state message when the user has no projects', async () => {
    mockListProjects.mockResolvedValueOnce([]);

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText(/no projects yet/i)).toBeDefined());
  });

  it('toggling a checkbox calls addProductToProject', async () => {
    const initial = project({ id: 'p1', name: 'Robot' });
    mockListProjects.mockResolvedValueOnce([initial]);
    mockAddProductToProject.mockResolvedValueOnce({
      ...initial,
      product_refs: [REF],
    });

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText('Robot')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByRole('checkbox'));
    });

    expect(mockAddProductToProject).toHaveBeenCalledWith('p1', REF);
  });

  it('toggling an already-checked project calls removeProductFromProject', async () => {
    const initial = project({ id: 'p1', name: 'Robot', product_refs: [REF] });
    mockListProjects.mockResolvedValueOnce([initial]);
    mockRemoveProductFromProject.mockResolvedValueOnce({
      ...initial,
      product_refs: [],
    });

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText('Robot')).toBeDefined());

    const checkbox = screen.getByRole('checkbox');
    expect((checkbox as HTMLInputElement).checked).toBe(true);

    await act(async () => {
      fireEvent.click(checkbox);
    });

    expect(mockRemoveProductFromProject).toHaveBeenCalledWith('p1', REF);
    expect(mockAddProductToProject).not.toHaveBeenCalled();
  });

  it('create flow creates a project and auto-adds the product', async () => {
    mockListProjects.mockResolvedValueOnce([]);
    const created = project({ id: 'p2', name: 'New Cell' });
    mockCreateProject.mockResolvedValueOnce(created);
    mockAddProductToProject.mockResolvedValueOnce({
      ...created,
      product_refs: [REF],
    });

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText(/no projects yet/i)).toBeDefined());

    fireEvent.change(screen.getByPlaceholderText(/new project name/i), {
      target: { value: 'New Cell' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /^create$/i }));
    });

    expect(mockCreateProject).toHaveBeenCalledWith('New Cell');
    expect(mockAddProductToProject).toHaveBeenCalledWith('p2', REF);
  });

  it('surfaces an error when toggling fails', async () => {
    mockListProjects.mockResolvedValueOnce([project({ id: 'p1', name: 'Robot' })]);
    mockAddProductToProject.mockRejectedValueOnce(new Error('Network down'));

    await act(async () => {
      wrap(<AddToProjectMenu productRef={REF} />);
    });

    fireEvent.click(screen.getByRole('button', { name: /add to project/i }));
    await waitFor(() => expect(screen.getByText('Robot')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByRole('checkbox'));
    });

    await waitFor(() => expect(screen.getByText(/network down/i)).toBeDefined());
  });
});
