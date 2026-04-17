/**
 * Admin operations — diff, promote, demote, purge — across dev/prod tables.
 *
 * This is the TypeScript counterpart to datasheetminer/admin/operations.py.
 * The semantics match: blacklist is enforced on promote only; demote has no
 * check; purge requires at least one filter (type and/or manufacturer).
 */

import { DynamoDBService } from '../db/dynamodb';
import { Datasheet, Manufacturer, Product, ProductType } from '../types/models';
import { Blacklist } from './blacklist';

// A "promotable" product is any Product union member except Datasheet.
// Datasheets live in the same table but are never moved by admin operations.
type PromotableProduct = Exclude<Product, Datasheet>;

export type Stage = 'dev' | 'staging' | 'prod';

const PROMOTABLE_PRODUCT_TYPES: ProductType[] = [
  'motor',
  'drive',
  'gearhead',
  'robot_arm',
];

export function makeService(stage: Stage): DynamoDBService {
  return new DynamoDBService({ tableName: `products-${stage}` });
}

function isPromotable(item: Product): item is PromotableProduct {
  return item.product_type !== 'datasheet' && 'product_id' in item;
}

async function listByType(
  db: DynamoDBService,
  productType: ProductType,
  manufacturer?: string
): Promise<PromotableProduct[]> {
  const items = await db.list(productType);
  const promotable = items.filter(isPromotable);
  if (!manufacturer) return promotable;
  return promotable.filter((p) => p.manufacturer === manufacturer);
}

// ── Result types ───────────────────────────────────────────────────

export interface DiffResult {
  product_type: ProductType;
  source_stage: Stage;
  target_stage: Stage;
  only_in_source: string[];
  only_in_target: string[];
  in_both_count: number;
}

export interface PromoteResult {
  product_type: ProductType;
  considered: number;
  blocked_by_blacklist: number;
  blocked_manufacturers: string[];
  promoted_products: number;
  promoted_manufacturers: number;
  applied: boolean;
}

export interface PurgeResult {
  stage: Stage;
  product_type: ProductType | null;
  manufacturer: string | null;
  matched: number;
  deleted: number;
  applied: boolean;
}

// ── Operations ─────────────────────────────────────────────────────

export async function diff(opts: {
  source: DynamoDBService;
  target: DynamoDBService;
  productType: ProductType;
  sourceStage: Stage;
  targetStage: Stage;
  manufacturer?: string;
}): Promise<DiffResult> {
  const { source, target, productType, sourceStage, targetStage, manufacturer } = opts;
  const [src, tgt] = await Promise.all([
    listByType(source, productType, manufacturer),
    listByType(target, productType, manufacturer),
  ]);

  const srcIds = new Set(src.map((p) => String(p.product_id)));
  const tgtIds = new Set(tgt.map((p) => String(p.product_id)));

  const onlySrc: string[] = [];
  const onlyTgt: string[] = [];
  let both = 0;
  for (const id of srcIds) {
    if (tgtIds.has(id)) both++;
    else onlySrc.push(id);
  }
  for (const id of tgtIds) {
    if (!srcIds.has(id)) onlyTgt.push(id);
  }

  return {
    product_type: productType,
    source_stage: sourceStage,
    target_stage: targetStage,
    only_in_source: onlySrc.sort(),
    only_in_target: onlyTgt.sort(),
    in_both_count: both,
  };
}

/** Manufacturer records tied to the given product set, optionally filtered
 *  by a blacklist. Only returns manufacturers whose `name` matches a product
 *  being moved — keeps the target table free of orphan records. */
async function manufacturersTiedTo(
  source: DynamoDBService,
  products: PromotableProduct[],
  blacklist?: Blacklist
): Promise<Manufacturer[]> {
  const names = new Set(products.map((p) => p.manufacturer).filter(Boolean) as string[]);
  if (names.size === 0) return [];
  const all = await source.listManufacturers();
  return all.filter((m) => {
    if (!names.has(m.name)) return false;
    if (blacklist && blacklist.contains(m.name)) return false;
    return true;
  });
}

export async function promote(opts: {
  source: DynamoDBService;
  target: DynamoDBService;
  productType: ProductType;
  blacklist: Blacklist;
  manufacturer?: string;
  apply: boolean;
}): Promise<PromoteResult> {
  const { source, target, productType, blacklist, manufacturer, apply } = opts;
  const products = await listByType(source, productType, manufacturer);

  const blocked: string[] = [];
  const toWrite: PromotableProduct[] = [];
  for (const p of products) {
    if (p.manufacturer && blacklist.contains(p.manufacturer)) {
      blocked.push(p.manufacturer);
    } else {
      toWrite.push(p);
    }
  }

  const manufacturers = await manufacturersTiedTo(source, toWrite, blacklist);

  let promotedProducts = 0;
  let promotedManufacturers = 0;
  if (apply) {
    if (toWrite.length > 0) {
      promotedProducts = await target.batchCreate(toWrite);
    }
    if (manufacturers.length > 0) {
      promotedManufacturers = await target.batchCreateManufacturers(manufacturers);
    }
  } else {
    promotedProducts = toWrite.length;
    promotedManufacturers = manufacturers.length;
  }

  return {
    product_type: productType,
    considered: products.length,
    blocked_by_blacklist: blocked.length,
    blocked_manufacturers: Array.from(new Set(blocked)).sort(),
    promoted_products: promotedProducts,
    promoted_manufacturers: promotedManufacturers,
    applied: apply,
  };
}

export async function demote(opts: {
  source: DynamoDBService;
  target: DynamoDBService;
  productType: ProductType;
  manufacturer?: string;
  apply: boolean;
}): Promise<PromoteResult> {
  const { source, target, productType, manufacturer, apply } = opts;
  const products = await listByType(source, productType, manufacturer);

  // Demote has no blacklist check — rollback path always copies everything.
  const manufacturers = await manufacturersTiedTo(source, products);

  let promotedProducts = 0;
  let promotedManufacturers = 0;
  if (apply) {
    if (products.length > 0) {
      promotedProducts = await target.batchCreate(products);
    }
    if (manufacturers.length > 0) {
      promotedManufacturers = await target.batchCreateManufacturers(manufacturers);
    }
  } else {
    promotedProducts = products.length;
    promotedManufacturers = manufacturers.length;
  }

  return {
    product_type: productType,
    considered: products.length,
    blocked_by_blacklist: 0,
    blocked_manufacturers: [],
    promoted_products: promotedProducts,
    promoted_manufacturers: promotedManufacturers,
    applied: apply,
  };
}

export async function purge(opts: {
  db: DynamoDBService;
  stage: Stage;
  productType?: ProductType;
  manufacturer?: string;
  apply: boolean;
}): Promise<PurgeResult> {
  const { db, stage, productType, manufacturer, apply } = opts;
  if (!productType && !manufacturer) {
    throw new Error('purge requires at least one of product_type or manufacturer');
  }

  const typesToScan: ProductType[] = productType
    ? [productType]
    : PROMOTABLE_PRODUCT_TYPES;

  const matchedKeys: { PK: string; SK: string }[] = [];
  for (const t of typesToScan) {
    const items = await listByType(db, t, manufacturer);
    for (const p of items) {
      matchedKeys.push({
        PK: `PRODUCT#${t.toUpperCase()}`,
        SK: `PRODUCT#${p.product_id}`,
      });
    }
  }

  let deleted = 0;
  if (apply && matchedKeys.length > 0) {
    deleted = await db.batchDelete(matchedKeys);
  }

  return {
    stage,
    product_type: productType ?? null,
    manufacturer: manufacturer ?? null,
    matched: matchedKeys.length,
    deleted,
    applied: apply,
  };
}

/** The confirm string a purge --apply must exactly match. */
export function expectedPurgeConfirm(
  stage: Stage,
  productType?: ProductType,
  manufacturer?: string
): string {
  const parts: string[] = ['yes delete', stage];
  if (productType) parts.push(productType);
  if (manufacturer) parts.push(manufacturer);
  return parts.join(' ');
}

export { PROMOTABLE_PRODUCT_TYPES };
