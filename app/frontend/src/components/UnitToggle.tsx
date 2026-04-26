/**
 * Unit toggle component for switching between metric and imperial display.
 *
 * The switch is purely a viewing pref — DynamoDB stays canonical metric.
 * Compound coefficients (V/krpm, Nm/A, etc.) are shown as-is regardless
 * of toggle state because flipping half a unit would mislead.
 */

import { useApp } from '../context/AppContext';

export default function UnitToggle() {
  const { unitSystem, setUnitSystem } = useApp();
  const isImperial = unitSystem === 'imperial';

  const toggle = () => {
    setUnitSystem(isImperial ? 'metric' : 'imperial');
  };

  const title = isImperial
    ? 'Switch to metric display (compound coefficients shown as-is)'
    : 'Switch to imperial display (compound coefficients shown as-is)';

  return (
    <button
      className="theme-toggle unit-toggle"
      onClick={toggle}
      aria-label={isImperial ? 'Switch to metric units' : 'Switch to imperial units'}
      title={title}
    >
      <span
        style={{
          fontSize: '0.7rem',
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
