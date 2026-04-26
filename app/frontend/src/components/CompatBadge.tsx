/**
 * Small status badge for compatibility results. Two states only — fits-partial
 * mode means the API never returns 'fail'. Per-field detail rides in the
 * tooltip on hover/focus.
 */
import { CheckStatus } from '../types/compat';

interface CompatBadgeProps {
  status: CheckStatus;
  label?: string;
  detail?: string;
}

const STATUS_LABEL: Record<CheckStatus, string> = {
  ok: 'OK',
  partial: 'Check',
};

export default function CompatBadge({ status, label, detail }: CompatBadgeProps) {
  const text = label ?? STATUS_LABEL[status];
  return (
    <span
      className={`compat-badge compat-badge-${status}`}
      title={detail || text}
      aria-label={detail ? `${text}: ${detail}` : text}
    >
      {text}
    </span>
  );
}
