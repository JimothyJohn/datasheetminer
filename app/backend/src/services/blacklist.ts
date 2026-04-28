/**
 * Manufacturer blacklist — manufacturers banned from promotion to prod.
 *
 * Reads/writes the same JSON file the Python CLI uses
 * (specodex/admin/blacklist.py), so edits from either tool stay in sync.
 * File lives at repo root: admin/blacklist.json
 *
 * Comparison is case-insensitive: "ABB", "abb", and "Abb" all refer to the
 * same entry, and the first-added casing is preserved for display. This
 * prevents trivial bypass and matches the Python side.
 */

import fs from 'fs';
import path from 'path';

// Resolve to <repo_root>/admin/blacklist.json. This file lives at
// app/backend/src/services/blacklist.ts — four parents up is the repo root.
// Matches the pattern used by config/index.ts for loading .env.
const BLACKLIST_PATH = path.resolve(__dirname, '../../../..', 'admin', 'blacklist.json');

interface BlacklistFile {
  banned_manufacturers: string[];
}

export class Blacklist {
  private readonly filePath: string;
  // Map from lowercased name → original casing. First-added wins on collision.
  private banned: Map<string, string>;

  constructor(filePath: string = BLACKLIST_PATH) {
    this.filePath = filePath;
    this.banned = new Map();
    this.load();
  }

  load(): void {
    if (!fs.existsSync(this.filePath)) {
      this.banned = new Map();
      return;
    }
    const raw = fs.readFileSync(this.filePath, 'utf-8');
    const parsed = JSON.parse(raw) as BlacklistFile;
    if (!Array.isArray(parsed.banned_manufacturers)) {
      throw new Error(
        `${this.filePath}: 'banned_manufacturers' must be an array of strings`
      );
    }
    this.banned = new Map();
    for (const rawName of parsed.banned_manufacturers) {
      const name = String(rawName);
      const key = name.toLowerCase();
      // Preserve first occurrence's casing if the file has duplicates.
      if (!this.banned.has(key)) this.banned.set(key, name);
    }
  }

  save(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const payload: BlacklistFile = {
      banned_manufacturers: this.names(),
    };
    fs.writeFileSync(this.filePath, JSON.stringify(payload, null, 2) + '\n');
  }

  /** Returns true if newly added, false if already present (case-insensitive). */
  add(name: string): boolean {
    const key = name.toLowerCase();
    if (this.banned.has(key)) return false;
    this.banned.set(key, name);
    return true;
  }

  /** Returns true if removed, false if not present (case-insensitive). */
  remove(name: string): boolean {
    const key = name.toLowerCase();
    if (!this.banned.has(key)) return false;
    this.banned.delete(key);
    return true;
  }

  /** Case-insensitive membership check. */
  contains(name: string): boolean {
    return this.banned.has(name.toLowerCase());
  }

  /** Returns the stored (display) names, sorted case-insensitively. */
  names(): string[] {
    return [...this.banned.values()].sort((a, b) =>
      a.toLowerCase().localeCompare(b.toLowerCase())
    );
  }

  get size(): number {
    return this.banned.size;
  }
}

export const BLACKLIST_FILE_PATH = BLACKLIST_PATH;
