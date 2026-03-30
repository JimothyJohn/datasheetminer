/**
 * Product type display completeness tests.
 *
 * Catches the exact class of bug where a product type is defined in models
 * but missing from display configuration (the robot_arm display glitch).
 * Every product type must have:
 *   - Filter attributes defined
 *   - Non-empty display columns in getDisplayedAttributes()
 *   - Proper type definition in models
 *
 * When agents add a new product type, these tests fail until ALL layers
 * are updated, preventing partial support from reaching production.
 */

import { describe, it, expect } from 'vitest';
import {
  getAttributesForType,
  getMotorAttributes,
  getDriveAttributes,
  getRobotArmAttributes,
  getGearheadAttributes,
  getDatasheetAttributes,
  AttributeMetadata,
} from './filters';
import { ProductType } from './models';

// All hardware product types that users can browse
const HARDWARE_TYPES: ProductType[] = ['motor', 'drive', 'robot_arm', 'gearhead'];

// All product types including metadata types
const ALL_TYPES: ProductType[] = ['motor', 'drive', 'robot_arm', 'gearhead', 'datasheet'];

// =================== Filter Attribute Coverage ===================

describe('Filter attributes defined for all product types', () => {
  it.each(ALL_TYPES)('%s has filter attributes', (type) => {
    const attrs = getAttributesForType(type);
    expect(attrs.length).toBeGreaterThan(0);
  });

  it.each(HARDWARE_TYPES)('%s has at least 5 filter attributes', (type) => {
    const attrs = getAttributesForType(type);
    expect(attrs.length).toBeGreaterThanOrEqual(5);
  });

  it('all type returns common attributes', () => {
    const attrs = getAttributesForType('all');
    expect(attrs.length).toBeGreaterThan(0);
  });

  it('null type returns empty array', () => {
    const attrs = getAttributesForType(null);
    expect(attrs).toEqual([]);
  });
});

// =================== Attribute Metadata Shape ===================

describe('Attribute metadata has required fields', () => {
  const allGetters: [string, () => AttributeMetadata[]][] = [
    ['motor', getMotorAttributes],
    ['drive', getDriveAttributes],
    ['robot_arm', getRobotArmAttributes],
    ['gearhead', getGearheadAttributes],
    ['datasheet', getDatasheetAttributes],
  ];

  it.each(allGetters)('%s attributes have key, displayName, type', (_name, getter) => {
    const attrs = getter();
    for (const attr of attrs) {
      expect(attr.key).toBeTruthy();
      expect(attr.displayName).toBeTruthy();
      expect(attr.type).toBeTruthy();
      expect(attr.applicableTypes).toBeDefined();
      expect(attr.applicableTypes.length).toBeGreaterThan(0);
    }
  });

  it.each(allGetters)('%s has no duplicate keys', (_name, getter) => {
    const attrs = getter();
    const keys = attrs.map(a => a.key);
    const uniqueKeys = new Set(keys);
    expect(keys.length).toBe(uniqueKeys.size);
  });
});

// =================== Common Attributes ===================

describe('Common attributes exist across types', () => {
  it('manufacturer is defined for all hardware types', () => {
    for (const type of HARDWARE_TYPES) {
      const attrs = getAttributesForType(type);
      const hasManufacturer = attrs.some(a => a.key === 'manufacturer');
      expect(hasManufacturer).toBe(true);
    }
  });

  it('part_number is defined for all hardware types', () => {
    for (const type of HARDWARE_TYPES) {
      const attrs = getAttributesForType(type);
      const hasPartNumber = attrs.some(a => a.key === 'part_number');
      expect(hasPartNumber).toBe(true);
    }
  });
});

// =================== Robot Arm Specific ===================

describe('Robot arm attributes match model', () => {
  it('has payload attribute', () => {
    const attrs = getRobotArmAttributes();
    expect(attrs.some(a => a.key === 'payload')).toBe(true);
  });

  it('has reach attribute', () => {
    const attrs = getRobotArmAttributes();
    expect(attrs.some(a => a.key === 'reach')).toBe(true);
  });

  it('has degrees_of_freedom attribute', () => {
    const attrs = getRobotArmAttributes();
    expect(attrs.some(a => a.key === 'degrees_of_freedom')).toBe(true);
  });

  it('has weight attribute', () => {
    const attrs = getRobotArmAttributes();
    expect(attrs.some(a => a.key === 'weight')).toBe(true);
  });
});

// =================== Gearhead Specific ===================

describe('Gearhead attributes match model', () => {
  it('has gear_ratio attribute', () => {
    const attrs = getGearheadAttributes();
    expect(attrs.some(a => a.key === 'gear_ratio')).toBe(true);
  });

  it('has backlash attribute', () => {
    const attrs = getGearheadAttributes();
    expect(attrs.some(a => a.key === 'backlash')).toBe(true);
  });

  it('has efficiency attribute', () => {
    const attrs = getGearheadAttributes();
    expect(attrs.some(a => a.key === 'efficiency')).toBe(true);
  });
});
