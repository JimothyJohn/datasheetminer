/**
 * Tests for filter and sort logic
 */

import { describe, it, expect } from 'vitest';
import { applyFilters, sortProducts, FilterCriterion, SortConfig } from './filters';
import { Product } from './models';

describe('Filter Logic', () => {
  const mockProducts: Product[] = [
    {
      product_id: '1',
      product_type: 'motor',
      manufacturer: 'ACME',
      part_number: 'AC-100',
      rated_power: { value: 100, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#1',
    },
    {
      product_id: '2',
      product_type: 'motor',
      manufacturer: 'ACME',
      part_number: 'AC-200',
      rated_power: { value: 200, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#2',
    },
    {
      product_id: '3',
      product_type: 'motor',
      manufacturer: 'Beta Corp',
      part_number: 'BC-150',
      rated_power: { value: 150, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#3',
    },
  ];

  describe('applyFilters', () => {
    it('should return all products when no filters applied', () => {
      const result = applyFilters(mockProducts, []);
      expect(result).toEqual(mockProducts);
    });

    it('should filter by exact string match (include mode)', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'manufacturer',
          mode: 'include',
          value: 'ACME',
          displayName: 'Manufacturer',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(2);
      expect(result.every(p => p.manufacturer === 'ACME')).toBe(true);
    });

    it('should filter by partial string match (case insensitive)', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'manufacturer',
          mode: 'include',
          value: 'acme',
          displayName: 'Manufacturer',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(2);
    });

    it('should exclude products (exclude mode)', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'manufacturer',
          mode: 'exclude',
          value: 'ACME',
          displayName: 'Manufacturer',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(1);
      expect(result[0].manufacturer).toBe('Beta Corp');
    });

    it('should filter by numeric value with equals operator', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'rated_power',
          mode: 'include',
          value: 100,
          operator: '=',
          displayName: 'Rated Power',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(1);
      expect(result[0].product_id).toBe('1');
    });

    it('should filter by numeric value with greater than operator', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'rated_power',
          mode: 'include',
          value: 150,
          operator: '>',
          displayName: 'Rated Power',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(1);
      expect(result[0].product_id).toBe('2');
    });

    it('should filter by numeric value with less than operator', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'rated_power',
          mode: 'include',
          value: 150,
          operator: '<',
          displayName: 'Rated Power',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(1);
      expect(result[0].product_id).toBe('1');
    });

    it('should handle multiple filters (AND logic)', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'manufacturer',
          mode: 'include',
          value: 'ACME',
          displayName: 'Manufacturer',
        },
        {
          attribute: 'rated_power',
          mode: 'include',
          value: 150,
          operator: '>',
          displayName: 'Rated Power',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(1);
      expect(result[0].product_id).toBe('2');
    });

    it('should ignore neutral mode filters', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'manufacturer',
          mode: 'neutral',
          value: 'ACME',
          displayName: 'Manufacturer',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toEqual(mockProducts);
    });

    it('should handle missing attributes gracefully', () => {
      const filters: FilterCriterion[] = [
        {
          attribute: 'nonexistent',
          mode: 'include',
          value: 'test',
          displayName: 'Nonexistent',
        },
      ];
      const result = applyFilters(mockProducts, filters);
      expect(result).toHaveLength(0);
    });
  });
});

describe('Sort Logic', () => {
  const mockProducts: Product[] = [
    {
      product_id: 'abc10',
      product_type: 'motor',
      manufacturer: 'ACME',
      part_number: 'AC-100',
      rated_power: { value: 100, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#abc10',
    },
    {
      product_id: 'abc2',
      product_type: 'motor',
      manufacturer: 'ACME',
      part_number: 'AC-200',
      rated_power: { value: 200, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#abc2',
    },
    {
      product_id: 'abc3',
      product_type: 'motor',
      manufacturer: 'Beta Corp',
      part_number: 'BC-150',
      rated_power: { value: 150, unit: 'W' },
      PK: 'PRODUCT#MOTOR',
      SK: 'PRODUCT#abc3',
    },
  ];

  describe('sortProducts', () => {
    it('should return unsorted products when sort is null', () => {
      const result = sortProducts(mockProducts, null);
      expect(result).toEqual(mockProducts);
    });

    it('should sort by string alphabetically (ascending)', () => {
      const sort: SortConfig = {
        attribute: 'manufacturer',
        direction: 'asc',
        displayName: 'Manufacturer',
      };
      const result = sortProducts(mockProducts, sort);
      expect(result[0].manufacturer).toBe('ACME');
      expect(result[2].manufacturer).toBe('Beta Corp');
    });

    it('should sort by string alphabetically (descending)', () => {
      const sort: SortConfig = {
        attribute: 'manufacturer',
        direction: 'desc',
        displayName: 'Manufacturer',
      };
      const result = sortProducts(mockProducts, sort);
      expect(result[0].manufacturer).toBe('Beta Corp');
      expect(result[2].manufacturer).toBe('ACME');
    });

    it('should sort by numeric value (ascending)', () => {
      const sort: SortConfig = {
        attribute: 'rated_power',
        direction: 'asc',
        displayName: 'Rated Power',
      };
      const result = sortProducts(mockProducts, sort);
      expect(result[0].product_id).toBe('abc10');
      expect(result[1].product_id).toBe('abc3');
      expect(result[2].product_id).toBe('abc2');
    });

    it('should sort by numeric value (descending)', () => {
      const sort: SortConfig = {
        attribute: 'rated_power',
        direction: 'desc',
        displayName: 'Rated Power',
      };
      const result = sortProducts(mockProducts, sort);
      expect(result[0].product_id).toBe('abc2');
      expect(result[1].product_id).toBe('abc3');
      expect(result[2].product_id).toBe('abc10');
    });

    it('should use natural alphanumeric sorting (abc2 < abc10)', () => {
      const sort: SortConfig = {
        attribute: 'product_id',
        direction: 'asc',
        displayName: 'Product ID',
      };
      const result = sortProducts(mockProducts, sort);
      expect(result[0].product_id).toBe('abc2');
      expect(result[1].product_id).toBe('abc3');
      expect(result[2].product_id).toBe('abc10');
    });

    it('should handle multi-level sorting', () => {
      const productsWithDuplicates: Product[] = [
        {
          product_id: '1',
          product_type: 'motor',
          manufacturer: 'ACME',
          part_number: 'AC-200',
          rated_power: { value: 100, unit: 'W' },
          PK: 'PRODUCT#MOTOR',
          SK: 'PRODUCT#1',
        },
        {
          product_id: '2',
          product_type: 'motor',
          manufacturer: 'ACME',
          part_number: 'AC-100',
          rated_power: { value: 100, unit: 'W' },
          PK: 'PRODUCT#MOTOR',
          SK: 'PRODUCT#2',
        },
        {
          product_id: '3',
          product_type: 'motor',
          manufacturer: 'Beta Corp',
          part_number: 'BC-150',
          rated_power: { value: 200, unit: 'W' },
          PK: 'PRODUCT#MOTOR',
          SK: 'PRODUCT#3',
        },
      ];

      const sorts: SortConfig[] = [
        {
          attribute: 'rated_power',
          direction: 'asc',
          displayName: 'Rated Power',
        },
        {
          attribute: 'part_number',
          direction: 'asc',
          displayName: 'Part Number',
        },
      ];

      const result = sortProducts(productsWithDuplicates, sorts);
      
      // First sorted by rated_power (both 100W come first)
      // Then sorted by part_number (AC-100 before AC-200)
      expect(result[0].part_number).toBe('AC-100');
      expect(result[1].part_number).toBe('AC-200');
      expect(result[2].part_number).toBe('BC-150');
    });

    it('should handle null values (push to end)', () => {
      const productsWithNull: Product[] = [
        {
          product_id: '1',
          product_type: 'motor',
          manufacturer: 'ACME',
          part_number: 'AC-100',
          PK: 'PRODUCT#MOTOR',
          SK: 'PRODUCT#1',
        },
        {
          product_id: '2',
          product_type: 'motor',
          manufacturer: 'Beta Corp',
          part_number: 'BC-150',
          rated_power: { value: 150, unit: 'W' },
          PK: 'PRODUCT#MOTOR',
          SK: 'PRODUCT#2',
        },
      ];

      const sort: SortConfig = {
        attribute: 'rated_power',
        direction: 'asc',
        displayName: 'Rated Power',
      };

      const result = sortProducts(productsWithNull, sort);
      expect(result[0].product_id).toBe('2'); // Has value
      expect(result[1].product_id).toBe('1'); // Null value goes last
    });

    it('should not mutate original array', () => {
      const original = [...mockProducts];
      const sort: SortConfig = {
        attribute: 'manufacturer',
        direction: 'desc',
        displayName: 'Manufacturer',
      };
      
      sortProducts(mockProducts, sort);
      expect(mockProducts).toEqual(original);
    });
  });
});
