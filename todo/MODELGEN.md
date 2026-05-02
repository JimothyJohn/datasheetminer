# MODELGEN — Pydantic → TypeScript codegen

> Single source of truth for the **type contract** between
> `specodex/models/*.py` and the frontend. Started as Phase 0 of
> [PYTHON_BACKEND.md](PYTHON_BACKEND.md); split into its own doc
> 2026-05-02 because the codegen ships independently of the larger
> Express → FastAPI migration and is worth tracking on its own.
>
> **Date drafted:** 2026-05-02. **Status:** 🚧 Phase 0 (toolchain) ✅
> shipped, Phase 0a (drift gate) ✅ shipped; consumer rewire and Zod
> enum collapse pending.

---

## What it is

Today: TypeScript interfaces in `app/{backend,frontend}/src/types/models.ts`
are hand-typed to mirror Pydantic models in `specodex/models/*.py`. CLAUDE.md
spells out the six-place runbook for adding a new product type. Three of those
places are typed-by-hand and silently drift.

End-state: one command (`./Quickstart gen-types`) regenerates
`app/frontend/src/types/generated.ts` from Pydantic. Hand-typed `models.ts`
becomes a thin re-export shim. The backend Zod enum is derived from the same
generated artifact. Adding a product type collapses from 6 files to 2 + a
codegen run.

---

## Status

| Phase | Scope | State |
|---|---|---|
| **0** | `pydantic-to-typescript` dep, `scripts/gen_types.py`, `./Quickstart gen-types`, CLAUDE.md docs | ✅ shipped 2026-05-02 |
| **0a-i** | `generated.ts` committed, `test-codegen` CI gate, `models.ts` migration banner | ✅ shipped 2026-05-02 |
| **0a-ii** | Frontend `models.ts` rewritten to re-export from `generated.ts`; consumer fix-ups | ⏳ pending |
| **0b** | Backend `routes/search.ts` Zod enum + `config/productTypes.ts` allowlist derived from generated | ⏳ pending (depends on 0a-ii or can be done in parallel) |
| **0c** | "Adding a new product type" runbook collapses to 2 files + `gen-types` run | ⏳ pending (paperwork, lands with 0a-ii) |

`app/backend/src/types/models.ts` is **deliberately not migrated** —
the Express backend is slated for deletion in PYTHON_BACKEND.md Phase 3,
so rewiring it is wasted work.

---

## Phase 0a-ii — frontend rewire (the real work that's left)

### Why it isn't a one-line re-export

The generated shapes diverge from hand-typed in five places. Each needs a
paired consumer pass:

1. **`product_id?: string`** (generated, optional because Pydantic has
   `default_factory=uuid4`) vs **`product_id: string`** (hand, required).
   Consumers that treat it as guaranteed-present (`product.product_id.toLowerCase()`)
   need narrowing or a `?? ''` fallback.
2. **`product_name: string`** (generated, required because Pydantic
   `Field(...)`) vs **`product_name?: string`** (hand, optional). Consumers
   passing `Partial<Product>` may need a type relaxation. Constructors
   omitting `product_name` will fail tsc.
3. **`?: T | null`** (generated, every Optional field) vs **`?: T`**
   (hand, no `null` in the union). Consumers narrowing on truthy checks
   already handle this; consumers feeding into typed children may need
   `?? undefined`.
4. **`Manufacturer.PK: string`** (generated, required by `@computed_field`)
   vs **`PK?: string`** (hand, optional). Construction sites that don't
   set PK will break. Two mitigations: drop `@computed_field` for `PK`/`SK`
   in `ProductBase` (compute on read in the API), or change consumers.
5. **`ProductBase.datasheet_url?: string | null`** (generated) vs
   **`datasheet_url?: DatasheetLink`** (hand, an object with `.url` and
   `.pages`). Easier than it looks: `ProductDetailModal.tsx:209-211`
   already handles both shapes defensively. The migration is a
   `.url`-stripping pass at read sites + dropping `DatasheetLink`.

### Scope of consumer changes

Files that import from `../types/models` (per `grep -rn "from.*types/models"`):

```
app/frontend/src/api/client.ts              # Product, ProductSummary, ProductType, DatasheetEntry
app/frontend/src/context/AppContext.tsx     # DatasheetEntry, Product, ProductSummary, ProductType
app/frontend/src/components/DatasheetList.tsx
app/frontend/src/components/DatasheetEditModal.tsx
app/frontend/src/components/DatasheetFilterBar.tsx
app/frontend/src/components/ProductList.tsx
app/frontend/src/components/ProductDetailModal.tsx
app/frontend/src/components/AddToProjectMenu.tsx (in-flight)
app/frontend/src/components/ProjectsPage.tsx     (in-flight)
app/frontend/src/context/ProjectsContext.tsx     (in-flight)
…etc
```

The `(in-flight)` files belong to the Projects feature still landing on
master. **Don't start 0a-ii until Projects ships** — concurrent edits to
the same context file ask for merge pain.

### Suggested order (smallest blast first)

1. **`Manufacturer`** — narrow consumer surface, lives mostly in admin
   pages. Decide whether to drop `@computed_field` for `PK`/`SK` (the
   cleaner fix) and propagate.
2. **`ContactorPowerRating`, `ContactorIcwRating`, `ElectricCylinder`,
   `LinearActuator`** — leaf interfaces with small consumer surfaces.
3. **`Datasheet` / `DatasheetLink` / `DatasheetEntry`** — the
   `datasheet_url` reshape. `DatasheetEntry` stays hand-typed (frontend
   view type, not a Pydantic model).
4. **`Motor`, `Drive`, `Gearhead`, `RobotArm`, `Contactor`** — the big
   product-type interfaces. Tackle `ProductBase` here too (PK/SK
   computed-field decision).
5. **`Product` union, `ProductType` literal** — these aren't generated
   directly by `pydantic2ts`. Either keep them hand-typed in the shim,
   or have `gen_types.py` emit them as a postscript (extract from the
   `Literal[...]` in `specodex/models/common.py:ProductType`).

Each step: run `./Quickstart verify`. Green = ship.

---

## Phase 0b — Zod enum + allowlist collapse

`app/backend/src/routes/search.ts` defines a Zod enum that mirrors the
`ProductType` literal. `app/backend/src/config/productTypes.ts` defines
`VALID_PRODUCT_TYPES`. Both are silently-drift-prone.

**Solution:** `gen_types.py` already knows `ProductType` (it imports
`specodex.models.common`). Have it write a small TS module —
`app/frontend/src/types/generated_constants.ts` — exporting:

```ts
export const PRODUCT_TYPES = [
  'motor', 'drive', 'gearhead', 'robot_arm',
  'factory', 'datasheet', 'contactor',
  'electric_cylinder', 'linear_actuator',
] as const;
export type ProductType = (typeof PRODUCT_TYPES)[number];
```

Then:
- `app/backend/src/config/productTypes.ts` becomes
  `export { PRODUCT_TYPES as VALID_PRODUCT_TYPES } from '@frontend/.../generated_constants';`
  (or duplicate the constant array — backend has no path mapping today).
- `app/backend/src/routes/search.ts` Zod enum becomes
  `z.enum(PRODUCT_TYPES)`.

**Caveat:** the backend can't import from `app/frontend/src/...` without
adding a path alias or relocating the generated file. Two options:
- Generate two files: `app/frontend/src/types/generated.ts` and
  `app/backend/src/types/generated_constants.ts` (duplicates).
- Move `generated_constants.ts` to a shared location like
  `app/shared/types/` and add path aliases. **Don't bother** — Express
  is going away in PYTHON_BACKEND.md Phase 3, so the backend lift is
  short-lived. Duplicate is cheaper.

---

## Phase 0c — runbook collapse

After 0a-ii + 0b ship, edit CLAUDE.md "Adding a new product type" from
six steps to:

1. `specodex/models/<type>.py` — Pydantic model.
2. `specodex/models/common.py` — add `"<type>"` to `ProductType`.
3. `./Quickstart gen-types` — regenerates the TS contract.

Steps 3-6 (TS interface, Zod enum, allowlist, frontend union) all become
generated.

---

## Open questions

1. **`@computed_field` for `PK`/`SK`.** Generated TS marks them required,
   which breaks Manufacturer construction. Decision: drop the
   computed-field decorator and compute PK/SK on read in the API? Or
   keep it and force consumers to always set PK/SK? Lean toward dropping
   — the field is derivable, not authoritative.
2. **`Product` union codegen.** `pydantic2ts` doesn't emit unions. Do we
   write a small postscript in `gen_types.py` that walks
   `SCHEMA_CHOICES` and emits `export type Product = Motor | Drive | …`?
   Yes, probably — it's three lines and seals the last hand-typed gap.
3. **`generated_constants.ts` vs path-aliased shared module.** As above
   — defer; duplicate while Express is alive.

---

## Don't do this in MODELGEN

- **Don't migrate `app/backend/src/types/models.ts`.** Express is dying
  in PYTHON_BACKEND.md Phase 3.
- **Don't introduce OpenAPI codegen for a TypeScript API client.** That
  belongs to PYTHON_BACKEND.md Phase 1 (FastAPI cutover).
- **Don't reshape Pydantic models to make TS happier.** The Pydantic
  model is the source of truth; if a TS field looks ugly, fix the TS
  consumer.

---

## Triggers

If your task touches any of these, surface this doc:

- `specodex/models/*.py` — any field rename / add / remove.
- `specodex/models/common.py:ProductType` — adding a product type.
- `app/frontend/src/types/{models,generated}.ts` — direct edits.
- `app/backend/src/routes/search.ts` Zod enum or
  `app/backend/src/config/productTypes.ts`.
- `scripts/gen_types.py` — codegen tweaks.
- `./Quickstart gen-types` failures in CI (the `test-codegen` job).
- Mentions of "pydantic2ts", "generated.ts", "drift", "schema sync".

---

## References

- `todo/PYTHON_BACKEND.md` — bigger plan; Phase 0 lives here now.
- `todo/REFACTOR.md` §4.2, §4.5 — the audit findings this operationalises.
- `scripts/gen_types.py` — the codegen wrapper.
- `pydantic-to-typescript` — https://github.com/phillipdupuis/pydantic-to-typescript
