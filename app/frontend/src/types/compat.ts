/**
 * Shape of the compatibility report returned by POST /api/v1/compat/check.
 * Mirrors app/backend/src/services/compat.ts. In fits-partial mode the API
 * never returns 'fail' — what would have been a hard mismatch is surfaced as
 * 'partial' with the same per-field detail string.
 */
export type CheckStatus = 'ok' | 'partial';

export interface CheckResult {
  field: string;
  status: CheckStatus;
  detail: string;
}

export interface CompatResult {
  from_port: string;
  to_port: string;
  status: CheckStatus;
  checks: CheckResult[];
}

export interface CompatibilityReport {
  from_type: string;
  to_type: string;
  status: CheckStatus;
  results: CompatResult[];
}
