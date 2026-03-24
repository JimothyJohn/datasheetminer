import { useState } from 'react';
import { apiClient } from '../api/client';
import { useApp } from '../context/AppContext';

/**
 * PDF upload form — available on the public site.
 * Queues a PDF for extraction without modifying existing data.
 */
export default function UploadDatasheet() {
  const { categories, loadCategories } = useApp();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);
  const [form, setForm] = useState({
    product_name: '',
    manufacturer: '',
    product_type: '',
    pages: '',
  });

  const handleOpen = () => {
    if (!open) loadCategories();
    setOpen(!open);
    setStatus(null);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setSubmitting(true);
    setStatus(null);

    try {
      const pages = form.pages
        ? form.pages.split(',').map(p => parseInt(p.trim())).filter(n => !isNaN(n))
        : undefined;

      await apiClient.uploadPdf(file, {
        product_name: form.product_name,
        manufacturer: form.manufacturer,
        product_type: form.product_type,
        pages,
      });

      setStatus({ type: 'success', msg: 'PDF queued for extraction' });
      setForm({ product_name: '', manufacturer: '', product_type: '', pages: '' });
      setFile(null);
      setTimeout(() => { setOpen(false); setStatus(null); }, 2000);
    } catch (err) {
      setStatus({ type: 'error', msg: err instanceof Error ? err.message : 'Upload failed' });
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.5rem',
    borderRadius: '4px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    fontSize: '0.9rem',
  };

  return (
    <>
      <button
        onClick={handleOpen}
        style={{
          padding: '0.4rem 0.8rem',
          backgroundColor: 'var(--accent-color)',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '0.85rem',
          fontWeight: 500,
        }}
      >
        Upload PDF
      </button>

      {open && (
        <>
          <div
            onClick={() => setOpen(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 99, backgroundColor: 'rgba(0,0,0,0.3)' }}
          />
          <div style={{
            position: 'fixed',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 100,
            width: '400px',
            backgroundColor: 'var(--card-bg)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            boxShadow: '0 4px 20px var(--shadow-lg)',
            padding: '1.5rem',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0 }}>Upload Datasheet PDF</h3>
              <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.85rem', fontWeight: 500 }}>PDF File *</label>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={e => setFile(e.target.files?.[0] || null)}
                  required
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.85rem', fontWeight: 500 }}>Product Name *</label>
                <input name="product_name" value={form.product_name} onChange={handleChange} required style={inputStyle} />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.85rem', fontWeight: 500 }}>Manufacturer *</label>
                <input name="manufacturer" value={form.manufacturer} onChange={handleChange} required style={inputStyle} />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.85rem', fontWeight: 500 }}>Product Type *</label>
                <select name="product_type" value={form.product_type} onChange={handleChange} required style={inputStyle}>
                  <option value="">Select type</option>
                  {categories.map(c => (
                    <option key={c.type} value={c.type}>{c.display_name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.85rem', fontWeight: 500 }}>Pages (optional)</label>
                <input name="pages" value={form.pages} onChange={handleChange} placeholder="e.g. 3, 4, 5" style={inputStyle} />
              </div>

              {status && (
                <div style={{
                  padding: '0.5rem',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                  backgroundColor: status.type === 'success' ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)',
                  color: 'white',
                }}>
                  {status.msg}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting || !file}
                style={{
                  padding: '0.6rem',
                  backgroundColor: 'var(--accent-color)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: submitting ? 'wait' : 'pointer',
                  fontWeight: 500,
                  marginTop: '0.5rem',
                }}
              >
                {submitting ? 'Uploading...' : 'Upload & Queue for Extraction'}
              </button>
            </form>
          </div>
        </>
      )}
    </>
  );
}
