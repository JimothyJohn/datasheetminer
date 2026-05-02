/**
 * ProjectsContext — per-user project list, fetched on login.
 *
 * Owns the canonical client-side list of the signed-in user's
 * projects. Re-fetches whenever the auth user changes (login/logout/
 * token refresh that swaps subs); clears to [] when logged out so
 * stale data doesn't leak across sessions.
 *
 * Mutations (create / addProduct / removeProduct) call the API and
 * splice the returned project back into local state — single round
 * trip per action, no over-fetching.
 */

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { apiClient } from '../api/client';
import { useAuth } from './AuthContext';
import type { Project, ProductRef } from '../types/projects';

interface ProjectsContextType {
  projects: Project[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createProject: (name: string) => Promise<Project>;
  renameProject: (projectId: string, name: string) => Promise<void>;
  deleteProject: (projectId: string) => Promise<void>;
  addProductTo: (projectId: string, ref: ProductRef) => Promise<void>;
  removeProductFrom: (projectId: string, ref: ProductRef) => Promise<void>;
  /** True if this product (type+id) appears in the given project. */
  isInProject: (projectId: string, ref: ProductRef) => boolean;
}

const ProjectsContext = createContext<ProjectsContextType | undefined>(undefined);

export function ProjectsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track the last sub we fetched for so a token-refresh that keeps the
  // same user doesn't trigger a re-fetch loop.
  const lastFetchedSubRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) {
      setProjects([]);
      lastFetchedSubRef.current = null;
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.listProjects();
      setProjects(list);
      lastFetchedSubRef.current = user.sub;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load projects';
      setError(msg);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!user) {
      setProjects([]);
      lastFetchedSubRef.current = null;
      return;
    }
    if (lastFetchedSubRef.current === user.sub) return;
    void refresh();
  }, [user, refresh]);

  const createProject = useCallback(async (name: string) => {
    const created = await apiClient.createProject(name);
    setProjects(prev => [...prev, created]);
    return created;
  }, []);

  const deleteProject = useCallback(async (projectId: string) => {
    await apiClient.deleteProject(projectId);
    setProjects(prev => prev.filter(p => p.id !== projectId));
  }, []);

  const renameProject = useCallback(async (projectId: string, name: string) => {
    const updated = await apiClient.renameProject(projectId, name);
    setProjects(prev => prev.map(p => (p.id === projectId ? updated : p)));
  }, []);

  const upsert = (updated: Project) =>
    setProjects(prev => prev.map(p => (p.id === updated.id ? updated : p)));

  const addProductTo = useCallback(async (projectId: string, ref: ProductRef) => {
    const updated = await apiClient.addProductToProject(projectId, ref);
    upsert(updated);
  }, []);

  const removeProductFrom = useCallback(async (projectId: string, ref: ProductRef) => {
    const updated = await apiClient.removeProductFromProject(projectId, ref);
    upsert(updated);
  }, []);

  const isInProject = useCallback(
    (projectId: string, ref: ProductRef) => {
      const project = projects.find(p => p.id === projectId);
      if (!project) return false;
      return project.product_refs.some(
        r => r.product_type === ref.product_type && r.product_id === ref.product_id,
      );
    },
    [projects],
  );

  return (
    <ProjectsContext.Provider
      value={{
        projects,
        loading,
        error,
        refresh,
        createProject,
        renameProject,
        deleteProject,
        addProductTo,
        removeProductFrom,
        isInProject,
      }}
    >
      {children}
    </ProjectsContext.Provider>
  );
}

export function useProjects(): ProjectsContextType {
  const ctx = useContext(ProjectsContext);
  if (!ctx) throw new Error('useProjects must be used within a ProjectsProvider');
  return ctx;
}
