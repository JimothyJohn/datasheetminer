/**
 * Unit toggle component for switching between metric and imperial display.
 *
 * The switch is purely a viewing pref — DynamoDB stays canonical metric.
 * Compound coefficients (V/krpm, Nm/A, etc.) are shown as-is regardless
 * of toggle state because flipping half a unit would mislead.
 */

import { useApp } from '../context/AppContext';

interface UnitToggleProps {
  /** Compact variant for inline use (e.g. filter sidebar). Defaults to the
   *  44×44 header chip. */
  compact?: boolean;
}

export default function UnitToggle({ compact = false }: UnitToggleProps) {
  const { unitSystem, setUnitSystem } = useApp();
  const isImperial = unitSystem === 'imperial';

  const toggle = () => {
    setUnitSystem(isImperial ? 'metric' : 'imperial');
  };

  const title = isImperial
    ? 'Switch to metric display (compound coefficients shown as-is)'
    : 'Switch to imperial display (compound coefficients shown as-is)';

  if (compact) {
    return (
      <button
        className="unit-toggle-compact"
        onClick={toggle}
        aria-label={isImperial ? 'Switch to metric units' : 'Switch to imperial units'}
        title={title}
      >
        <span className="unit-toggle-compact-pills">
          <span className={`unit-toggle-compact-pill${!isImperial ? ' active' : ''}`}>SI</span>
          <span className={`unit-toggle-compact-pill${isImperial ? ' active' : ''}`}>IMP</span>
        </span>
        <span className="unit-toggle-compact-caption" aria-hidden="true">UNITS</span>
      </button>
    );
  }

  return (
    <button
      className="theme-toggle unit-toggle"
      onClick={toggle}
      aria-label={isImperial ? 'Switch to metric units' : 'Switch to imperial units'}
      title={title}
    >
      <span
        style={{
          fontSize: '0.85rem',
          fontWeight: 700,
          letterSpacing: '0.04em',
          fontFamily: 'inherit',
        }}
      >
        {isImperial ? 'IMP' : 'SI'}
      </span>
    </button>
  );
}
