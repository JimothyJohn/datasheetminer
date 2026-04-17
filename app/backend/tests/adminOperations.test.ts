/**
 * Tests for admin operations (diff, promote, demote, purge) with a
 * hand-rolled fake DynamoDBService. No live DynamoDB, no network.
 */

import fs from 'fs';
import os from 'os';
import path from 'path';

import { DynamoDBService } from '../src/db/dynamodb';
import { Drive, Manufacturer, Product, ProductType } from '../src/types/models';
import { Blacklist } from '../src/services/blacklist';
import {
  demote,
  diff,
  expectedPurgeConfirm,
  promote,
  purge,
} from '../src/services/adminOperations';

function makeDrive(manufacturer: string, productId: string): Drive {
  return {
    product_id: productId,
    product_type: 'drive',
    product_name: `${manufacturer}-drive`,
    manufacturer,
    PK: 'PRODUCT#DRIVE',
    SK: `PRODUCT#${productId}`,
  } as Drive;
}

function tmpBlacklist(entries: string[] = []): Blacklist {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bl-ops-'));
  const file = path.join(dir, 'blacklist.json');
  fs.writeFileSync(file, JSON.stringify({ banned_manufacturers: entries }));
  return new Blacklist(file);
}

interface FakeState {
  productsByType: Partial<Record<ProductType, Product[]>>;
  manufacturers: Manufacturer[];
  writes: { products: Product[]; manufacturers: Manufacturer[] };
  deletes: { PK: string; SK: string }[];
}

function fakeService(state: Partial<FakeState> = {}): DynamoDBService {
  const s: FakeState = {
    productsByType: state.productsByType ?? {},
    manufacturers: state.manufacturers ?? [],
    writes: state.writes ?? { products: [], manufacturers: [] },
    deletes: state.deletes ?? [],
  };

  return {
    list: async (productType: ProductType) => s.productsByType[productType] ?? [],
    batchCreate: async (items: Product[]) => {
      s.writes.products.push(...items);
      return items.length;
    },
    batchDelete: async (keys: { PK: string; SK: string }[]) => {
      s.deletes.push(...keys);
      return keys.length;
    },
    listManufacturers: async () => s.manufacturers,
    batchCreateManufacturers: async (items: Manufacturer[]) => {
      s.writes.manufacturers.push(...items);
      return items.length;
    },
    // Not used by admin ops but DynamoDBService has many more methods; we
    // cast through unknown to expose only what the code under test calls.
  } as unknown as DynamoDBService;
}

describe('adminOperations.diff', () => {
  it('returns disjoint sets', async () => {
    const source = fakeService({
      productsByType: {
        drive: [makeDrive('ABB', 'a'), makeDrive('ABB', 'b')],
      },
    });
    const target = fakeService();

    const result = await diff({
      source,
      target,
      productType: 'drive',
      sourceStage: 'dev',
      targetStage: 'prod',
    });

    expect(result.only_in_source).toEqual(['a', 'b']);
    expect(result.only_in_target).toEqual([]);
    expect(result.in_both_count).toBe(0);
  });

  it('reports partial overlap', async () => {
    const common = makeDrive('ABB', 'shared');
    const source = fakeService({
      productsByType: { drive: [common, makeDrive('ABB', 'only-src')] },
    });
    const target = fakeService({
      productsByType: { drive: [common, makeDrive('XYZ', 'only-tgt')] },
    });

    const result = await diff({
      source,
      target,
      productType: 'drive',
      sourceStage: 'dev',
      targetStage: 'prod',
    });

    expect(result.only_in_source).toEqual(['only-src']);
    expect(result.only_in_target).toEqual(['only-tgt']);
    expect(result.in_both_count).toBe(1);
  });

  it('honors manufacturer filter', async () => {
    const source = fakeService({
      productsByType: {
        drive: [makeDrive('ABB', 'a'), makeDrive('Siemens', 'b')],
      },
    });
    const target = fakeService();

    const result = await diff({
      source,
      target,
      productType: 'drive',
      sourceStage: 'dev',
      targetStage: 'prod',
      manufacturer: 'ABB',
    });

    expect(result.only_in_source).toEqual(['a']);
  });
});

describe('adminOperations.promote', () => {
  it('dry run writes nothing', async () => {
    const state: FakeState = {
      productsByType: { drive: [makeDrive('ABB', '1')] },
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService(state);
    const target = fakeService();
    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(),
      apply: false,
    });
    expect(result.applied).toBe(false);
    expect(result.promoted_products).toBe(1); // dry-run count
    expect(state.writes.products).toHaveLength(0);
  });

  it('apply writes products', async () => {
    const targetState: FakeState = {
      productsByType: {},
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService({
      productsByType: {
        drive: [makeDrive('ABB', '1'), makeDrive('Siemens', '2')],
      },
    });
    const target = fakeService(targetState);

    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(),
      apply: true,
    });

    expect(result.applied).toBe(true);
    expect(result.promoted_products).toBe(2);
    expect(targetState.writes.products).toHaveLength(2);
  });

  it('blacklist blocks matching manufacturer', async () => {
    const targetState: FakeState = {
      productsByType: {},
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService({
      productsByType: {
        drive: [
          makeDrive('ABB', '1'),
          makeDrive('BadCo', '2'),
          makeDrive('ABB', '3'),
        ],
      },
    });
    const target = fakeService(targetState);

    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(['BadCo']),
      apply: true,
    });

    expect(result.considered).toBe(3);
    expect(result.blocked_by_blacklist).toBe(1);
    expect(result.blocked_manufacturers).toEqual(['BadCo']);
    expect(result.promoted_products).toBe(2);
    expect(targetState.writes.products.every((p) => p.manufacturer === 'ABB')).toBe(true);
  });

  it('blacklist match is case-insensitive', async () => {
    const source = fakeService({
      productsByType: { drive: [makeDrive('BadCo', '1')] },
    });
    const target = fakeService();
    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(['BADCO']),
      apply: false,
    });
    expect(result.blocked_by_blacklist).toBe(1);
    expect(result.promoted_products).toBe(0);
  });

  it('promotes only manufacturers tied to promoted products', async () => {
    const targetState: FakeState = {
      productsByType: {},
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService({
      productsByType: { drive: [makeDrive('ABB', '1')] },
      manufacturers: [
        { id: 'mfg-abb', name: 'ABB' },
        { id: 'mfg-orphan', name: 'OrphanCo' }, // not on any product
      ],
    });
    const target = fakeService(targetState);

    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(),
      apply: true,
    });

    expect(result.promoted_manufacturers).toBe(1);
    expect(targetState.writes.manufacturers).toHaveLength(1);
    expect(targetState.writes.manufacturers[0].name).toBe('ABB');
  });

  it('skips blacklisted manufacturers when moving Manufacturer records', async () => {
    const targetState: FakeState = {
      productsByType: {},
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService({
      productsByType: {
        drive: [makeDrive('ABB', '1'), makeDrive('BadCo', '2')],
      },
      manufacturers: [
        { id: 'mfg-abb', name: 'ABB' },
        { id: 'mfg-bad', name: 'BadCo' },
      ],
    });
    const target = fakeService(targetState);

    const result = await promote({
      source,
      target,
      productType: 'drive',
      blacklist: tmpBlacklist(['BadCo']),
      apply: true,
    });

    // Only ABB's manufacturer should be written; BadCo's product was blocked
    // so it's no longer in the "tied to promoted products" set anyway.
    expect(result.promoted_manufacturers).toBe(1);
    expect(targetState.writes.manufacturers.map((m) => m.name)).toEqual(['ABB']);
  });
});

describe('adminOperations.demote', () => {
  it('has no blacklist check', async () => {
    const targetState: FakeState = {
      productsByType: {},
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const source = fakeService({
      productsByType: { drive: [makeDrive('BadCo', '1')] },
    });
    const target = fakeService(targetState);

    const result = await demote({
      source,
      target,
      productType: 'drive',
      apply: true,
    });

    expect(result.promoted_products).toBe(1);
    expect(result.blocked_by_blacklist).toBe(0);
  });
});

describe('adminOperations.purge', () => {
  it('requires at least one filter', async () => {
    const db = fakeService();
    await expect(
      purge({ db, stage: 'dev', apply: false })
    ).rejects.toThrow(/at least one/);
  });

  it('dry run reports matches, no delete', async () => {
    const state: FakeState = {
      productsByType: {
        drive: [makeDrive('ABB', '1'), makeDrive('ABB', '2')],
      },
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const db = fakeService(state);

    const result = await purge({ db, stage: 'dev', productType: 'drive', apply: false });
    expect(result.matched).toBe(2);
    expect(result.deleted).toBe(0);
    expect(result.applied).toBe(false);
    expect(state.deletes).toHaveLength(0);
  });

  it('apply issues batch delete', async () => {
    const state: FakeState = {
      productsByType: {
        drive: [makeDrive('ABB', '1')],
      },
      manufacturers: [],
      writes: { products: [], manufacturers: [] },
      deletes: [],
    };
    const db = fakeService(state);

    const result = await purge({ db, stage: 'dev', productType: 'drive', apply: true });
    expect(result.applied).toBe(true);
    expect(result.deleted).toBe(1);
    expect(state.deletes).toEqual([{ PK: 'PRODUCT#DRIVE', SK: 'PRODUCT#1' }]);
  });

  it('manufacturer filter narrows matches', async () => {
    const db = fakeService({
      productsByType: {
        drive: [makeDrive('ABB', '1'), makeDrive('Siemens', '2')],
      },
    });
    const result = await purge({
      db,
      stage: 'dev',
      productType: 'drive',
      manufacturer: 'ABB',
      apply: false,
    });
    expect(result.matched).toBe(1);
  });
});

describe('expectedPurgeConfirm', () => {
  it('produces a scope-specific confirmation string', () => {
    expect(expectedPurgeConfirm('prod', 'drive', 'ABB')).toBe('yes delete prod drive ABB');
    expect(expectedPurgeConfirm('prod', 'drive')).toBe('yes delete prod drive');
    expect(expectedPurgeConfirm('prod', undefined, 'ABB')).toBe('yes delete prod ABB');
  });
});
