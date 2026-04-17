/**
 * Blacklist service tests — file I/O + case-insensitive semantics.
 */

import fs from 'fs';
import os from 'os';
import path from 'path';
import { Blacklist } from '../src/services/blacklist';

function tmpFile(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bl-test-'));
  return path.join(dir, 'blacklist.json');
}

describe('Blacklist', () => {
  describe('loading', () => {
    it('starts empty when file missing', () => {
      const bl = new Blacklist(path.join(os.tmpdir(), 'nonexistent-' + Date.now() + '.json'));
      expect(bl.size).toBe(0);
      expect(bl.names()).toEqual([]);
    });

    it('loads existing file', () => {
      const f = tmpFile();
      fs.writeFileSync(f, JSON.stringify({ banned_manufacturers: ['ACME', 'BadCo'] }));
      const bl = new Blacklist(f);
      expect(bl.size).toBe(2);
      expect(bl.contains('ACME')).toBe(true);
      expect(bl.contains('BadCo')).toBe(true);
    });

    it('throws on invalid format', () => {
      const f = tmpFile();
      fs.writeFileSync(f, JSON.stringify({ banned_manufacturers: 'not-a-list' }));
      expect(() => new Blacklist(f)).toThrow();
    });

    it('dedupes file duplicates on load, preserving first casing', () => {
      const f = tmpFile();
      fs.writeFileSync(
        f,
        JSON.stringify({ banned_manufacturers: ['ACME', 'acme', 'Acme'] })
      );
      const bl = new Blacklist(f);
      expect(bl.size).toBe(1);
      expect(bl.names()).toEqual(['ACME']);
    });
  });

  describe('add / remove', () => {
    it('add returns true for new, false for duplicate', () => {
      const bl = new Blacklist(tmpFile());
      expect(bl.add('ACME')).toBe(true);
      expect(bl.add('ACME')).toBe(false);
    });

    it('add is case-insensitive', () => {
      const bl = new Blacklist(tmpFile());
      expect(bl.add('ACME')).toBe(true);
      expect(bl.add('acme')).toBe(false); // already present
      expect(bl.add('Acme')).toBe(false);
      expect(bl.size).toBe(1);
      // First-added casing preserved.
      expect(bl.names()).toEqual(['ACME']);
    });

    it('remove is case-insensitive', () => {
      const bl = new Blacklist(tmpFile());
      bl.add('ACME');
      expect(bl.remove('acme')).toBe(true);
      expect(bl.size).toBe(0);
      expect(bl.remove('ACME')).toBe(false);
    });

    it('contains is case-insensitive', () => {
      const bl = new Blacklist(tmpFile());
      bl.add('ABB');
      expect(bl.contains('abb')).toBe(true);
      expect(bl.contains('Abb')).toBe(true);
      expect(bl.contains('AB B')).toBe(false);
    });
  });

  describe('save / round trip', () => {
    it('save writes sorted JSON that reloads identically', () => {
      const f = tmpFile();
      const bl = new Blacklist(f);
      bl.add('Zebra');
      bl.add('alpha');
      bl.add('Beta');
      bl.save();

      const raw = JSON.parse(fs.readFileSync(f, 'utf-8'));
      // Sorted case-insensitively (alpha < Beta < Zebra).
      expect(raw.banned_manufacturers).toEqual(['alpha', 'Beta', 'Zebra']);

      const fresh = new Blacklist(f);
      expect(fresh.names()).toEqual(['alpha', 'Beta', 'Zebra']);
    });

    it('save creates parent directory if missing', () => {
      const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bl-test-'));
      const nested = path.join(dir, 'a', 'b', 'blacklist.json');
      const bl = new Blacklist(nested);
      bl.add('ACME');
      bl.save();
      expect(fs.existsSync(nested)).toBe(true);
    });
  });
});
