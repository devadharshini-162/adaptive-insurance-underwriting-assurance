import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { AvailableUnderwriter, InsuranceCompany, Product } from '../services/api';

import { consumerProducts } from './ApplicationFlow';

export default function NewSubmission() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [companies, setCompanies] = useState<InsuranceCompany[]>([]);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [underwriters, setUnderwriters] = useState<AvailableUnderwriter[]>([]);
  const [underwriterId, setUnderwriterId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([api.getProducts(), api.getInsuranceCompanies()])
      .then(([availableProducts, availableCompanies]) => { setProducts(availableProducts); setCompanies(availableCompanies); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId || !companyId) return;
    api.getAvailableUnderwriters(companyId, selectedId)
      .then(setUnderwriters)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load available underwriters.'));
  }, [selectedId, companyId]);

  async function handleStart() {
    if (!selectedId) return;
    setCreating(true);
    setError('');
    try {
      const sub = await api.createSubmission(selectedId, companyId || undefined, underwriterId || undefined);
      const isConsumer = products.find(p => p.id === selectedId) && consumerProducts.has(products.find(p => p.id === selectedId)!.name);
      navigate(`/application/${sub.id}/${isConsumer ? 'risk' : 'business'}`);
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
      <p className="subtitle">Choose your insurance product, demonstration insurer, and an available underwriter before starting the application.</p>

      {error && <div className="error-box">{error}</div>}

      <div className="product-list">
        {products.length === 0 && <p>No products found. Run the seed script first.</p>}
        {products.map((p) => (
          <button
            key={p.id}
            className={`product-card ${selectedId === p.id ? 'selected' : ''}`}
            onClick={() => { setSelectedId(p.id); setCompanyId(null); setUnderwriterId(null); setUnderwriters([]); }}
          >
            <strong>{p.name}</strong>
            <span>{p.description}</span>
          </button>
        ))}
      </div>

      {selectedId && <section className="panel selection-panel"><h2>Choose an insurer</h2><p className="subtitle">The insurers below are demonstration data for this prototype.</p><div className="product-list compact-list">{companies.map((company) => <button key={company.id} className={`product-card ${companyId === company.id ? 'selected' : ''}`} onClick={() => { setCompanyId(company.id); setUnderwriterId(null); setUnderwriters([]); }}><strong>{company.name}</strong><span>{company.description}</span></button>)}</div></section>}

      {companyId && <section className="panel selection-panel"><h2>Choose an underwriter</h2>{underwriters.length === 0 ? <p className="empty">No available underwriter supports this insurer and product combination.</p> : <div className="product-list compact-list">{underwriters.map((underwriter) => <button key={underwriter.id} className={`product-card ${underwriterId === underwriter.id ? 'selected' : ''}`} onClick={() => setUnderwriterId(underwriter.id)}><strong>{underwriterId === underwriter.id ? '✓ ' : ''}{underwriter.name}</strong><span>{underwriter.specialization || underwriter.role_title}</span><span>{underwriter.company_name}</span><span>Supports {products.find((product) => product.id === selectedId)?.name}</span><span>{underwriter.years_experience ? `${underwriter.years_experience} years’ experience` : underwriter.role_title}</span><span>{underwriter.availability_status === 'available' ? '● Available' : 'Currently unavailable'}</span><span>{underwriter.professional_description}</span></button>)}</div>}</section>}

      <button
        className="btn-primary"
        disabled={!selectedId || !companyId || !underwriterId || creating}
        onClick={handleStart}
      >
        {creating ? 'Creating…' : 'Start Application →'}
      </button>
    </div>
  );
}
