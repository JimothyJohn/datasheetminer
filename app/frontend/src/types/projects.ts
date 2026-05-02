/**
 * Project types — mirrors app/backend/src/types/models.ts.
 *
 * A Project is a user-owned, named collection of product refs. Refs
 * are tuples of (product_type, product_id), not snapshots — the UI
 * dereferences them against the live products feed at render time.
 */

export interface ProductRef {
  product_type: string;
  product_id: string;
}

export interface Project {
  id: string;
  name: string;
  owner_sub: string;
  product_refs: ProductRef[];
  created_at: string;
  updated_at: string;
}
