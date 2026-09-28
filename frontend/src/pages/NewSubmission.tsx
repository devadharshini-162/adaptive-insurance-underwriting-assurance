import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { Product } from '../services/api';

export default function NewSubmission() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.getProducts()
      .then(setProducts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleStart() {
    if (!selectedId) return;
    setCreating(true);
    setError('');
    try {
      const sub = await api.createSubmission(selectedId);
      navigate(`/application/${sub.id}/business`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setCreating(false);
    }
  }

  if (loading) return <div className="page"><p>Loading products…</p></div>;

  return (
    <div className="page">
      <nav className="breadcrumb"><button className="link-btn" onClick={() => navigate('/customer')}>← My Applications</button></nav>
      <h1>New Application</h1>
      <p className="subtitle">Select an insurance product to begin the adaptive questionnaire.</p>

      {error && <div className="error-box">{error}</div>}

      <div className="product-list">
        {products.length === 0 && <p>No products found. Run the seed script first.</p>}
        {products.map((p) => (
          <button
            key={p.id}
            className={`product-card ${selectedId === p.id ? 'selected' : ''}`}
            onClick={() => setSelectedId(p.id)}
          >
            <strong>{p.name}</strong>
            <span>{p.description}</span>
          </button>
        ))}
      </div>

      <button
        className="btn-primary"
        disabled={!selectedId || creating}
        onClick={handleStart}
      >
        {creating ? 'Creating…' : 'Start Questionnaire →'}
      </button>
    </div>
  );
}
