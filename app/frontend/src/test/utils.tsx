/**
 * Test utilities and helpers
 */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { AppProvider } from '../context/AppContext';

// Mock AppProvider for testing
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return <AppProvider>{children}</AppProvider>;
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options });

export * from '@testing-library/react';
export { customRender as render };
