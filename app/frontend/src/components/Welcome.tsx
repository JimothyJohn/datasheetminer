import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import './Welcome.css';

const ISSUE_STAMP = `ISSUE 1 — ${new Date().getFullYear()}`;

const features = [
  {
    code: 'TM-01',
    title: 'Filter chips, not facets',
    body:
      'Every spec on every record is a chip. Click to constrain, click again to drop. ' +
      'No nested accordions, no "show more". The filter set is the data.',
  },
  {
    code: 'TM-02',
    title: 'Metric ↔ imperial, header toggle',
    body:
      'Display-layer conversion across the whole catalog — torque, force, length, ' +
      'temperature. The underlying value never moves; the unit you read does.',
  },
  {
    code: 'TM-03',
    title: 'Datasheet links on every row',
    body:
      'The PDF that produced the row is one click away. Verify a number, check ' +
      'a derate curve, copy a part code straight from the source.',
  },
  {
    code: 'TM-04',
    title: 'Rows export like a BOM',
    body:
      'Filter to a shortlist, export to CSV. Tabular numerics, canonical units, ' +
      'manufacturer + part number — drop it into a spec sheet without massage.',
  },
];

export default function Welcome() {
  useEffect(() => {
    const previous = document.title;
    document.title = 'Specodex — A product selection frontend that only an engineer could love';
    return () => {
      document.title = previous;
    };
  }, []);

  return (
    <div className="specodex-landing" data-issue={ISSUE_STAMP}>
      <div className="specodex-grain" aria-hidden="true" />

      <header className="specodex-band">
        <div className="specodex-band-inner">
          <span className="specodex-wordmark">SPECODEX</span>
          <span className="specodex-band-meta">
            <span className="specodex-band-spec">SPEC · ODEX</span>
            <span className="specodex-band-rule" aria-hidden="true" />
            <span className="specodex-band-stamp">{ISSUE_STAMP}</span>
          </span>
        </div>
      </header>

      <main className="specodex-main">
        <section className="specodex-hero">
          <div className="specodex-hero-tag">▮▮▮ FIELD MANUAL ▮▮▮</div>
          <h1 className="specodex-hero-title">
            A product selection frontend
            <br />
            that only an engineer could love.
          </h1>
          <p className="specodex-hero-sub">
            Industrial spec data — drives, motors, gearheads, contactors, actuators —
            indexed, filtered, and exportable. No marketing copy on the rows. No
            "request a quote" gates. The number you need, with the datasheet that
            produced it.
          </p>
          <div className="specodex-cta-row">
            <Link to="/" className="specodex-cta specodex-cta-primary">
              Browse the catalog →
            </Link>
            <a
              href="https://github.com/JimothyJohn/datasheetminer"
              className="specodex-cta specodex-cta-ghost"
              rel="noreferrer"
            >
              Source on GitHub
            </a>
          </div>
        </section>

        <section className="specodex-features" aria-label="What it does">
          <div className="specodex-divider">
            <span>▮▮▮ WHAT IT DOES ▮▮▮</span>
          </div>
          <ol className="specodex-feature-list">
            {features.map((f) => (
              <li key={f.code} className="specodex-feature">
                <div className="specodex-feature-head">
                  <span className="specodex-feature-code">{f.code}</span>
                  <h2 className="specodex-feature-title">{f.title}</h2>
                </div>
                <p className="specodex-feature-body">{f.body}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="specodex-footer">
        <div className="specodex-footer-inner">
          <span>Specodex is built on the Datasheetminer engine.</span>
          <span className="specodex-footer-rule" aria-hidden="true" />
          <Link to="/" className="specodex-footer-link">
            Enter the catalog
          </Link>
        </div>
      </footer>
    </div>
  );
}
