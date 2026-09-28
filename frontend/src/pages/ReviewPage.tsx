import { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import type { RequirementView, IngestResponse, DocumentOut, ExtractedFieldOut, AdditionalRequest } from '../services/api';

export default function ReviewPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [requirements, setRequirements] = useState<RequirementView[]>((location.state?.requirements || []) as RequirementView[]);
  
  const [uploadingFor, setUploadingFor] = useState<number | null>(null);
  const [results, setResults] = useState<Record<number, IngestResponse>>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [documentFields, setDocumentFields] = useState<Record<number, ExtractedFieldOut[]>>({});
  const [requests, setRequests] = useState<AdditionalRequest[]>([]);
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);
  const fieldLabel = (key: string) => ({ annual_revenue: 'Annual revenue', property_value: 'Property value', hazardous_materials: 'Hazardous materials', risk_level: 'Risk level', insured_name: 'Insured name' }[key] || 'Extracted information');

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!submissionId || requirements.length) return;
    api.getApplication(Number(submissionId))
      .then((state) => api.evaluate(state.submission.product_id, state.answers, state.profile))
      .then((result) => setRequirements(result.requirements))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unable to load document requirements.'));
  }, [submissionId, requirements.length]);

  const refreshDocuments = () => submissionId && api.getSubmissionDocuments(Number(submissionId)).then(setDocuments).catch(() => undefined);
  useEffect(() => { refreshDocuments(); }, [submissionId]);
  useEffect(() => { if (submissionId) api.getApplication(Number(submissionId)).then((state) => { setRequests(state.requests || []); setDecisionMessage(state.decision_message || null); }).catch(() => undefined); }, [submissionId]);

  const handleUploadClick = (reqId: number) => {
    setUploadingFor(reqId);
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !uploadingFor || !submissionId) return;

    setError('');
    const reqId = uploadingFor;
    
    try {
        const res = await api.uploadDocument(Number(submissionId), reqId, file);
        setResults((prev) => ({ ...prev, [reqId]: res }));
        refreshDocuments();
    } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
    } finally {
        setUploadingFor(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const allUploaded = requirements.every((requirement) =>
    results[requirement.requirement_id]?.status === 'processed' ||
    documents.some((document) => document.requirement_id === requirement.requirement_id && document.status === 'processed' && !document.replaced)
  );

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');
      await api.generateIssues(Number(submissionId));
      navigate('/customer');
    } catch (err: any) {
      setError(err.message || 'Error generating issues.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <nav className="breadcrumb">
        <button className="link-btn" onClick={() => navigate(-1)}>← Back</button>
        <span> / Upload documents</span>
      </nav>
      <h1>Document upload</h1>
      <p className="subtitle">Upload the documents needed to complete your application.</p>
      
      {error && <div className="error-box">{error}</div>}
      {decisionMessage && <div className="panel"><h2>Underwriting update</h2><p>{decisionMessage}</p></div>}

      {requests.filter((request) => request.status === 'open').length > 0 && <section className="panel"><h2>Action required</h2>{requests.filter((request) => request.status === 'open').map((request) => <div className="document-card" key={request.id}><strong>{request.type === 'document' ? request.document_name : 'Additional information requested'}</strong><p>{request.message}</p>{request.note && <p>{request.note}</p>}{request.type === 'document' && <label className="btn-secondary">Upload requested document<input hidden type="file" accept="application/pdf,image/jpeg,image/png,image/webp,image/tiff" onChange={async (event) => { const file = event.target.files?.[0]; if (!file || !submissionId) return; try { await api.uploadRequestedDocument(Number(submissionId), request.id, file); const state = await api.getApplication(Number(submissionId)); setRequests(state.requests || []); refreshDocuments(); } catch (err) { setError(err instanceof Error ? err.message : 'Unable to upload the requested document.'); } }} /></label>}</div>)}</section>}

      <div className="requirements-list">
        {requirements.length === 0 && !loading && <p>No documents required. Please proceed.</p>}
        {requirements.map((req) => {
          const res = results[req.requirement_id];
          const isUploading = uploadingFor === req.requirement_id;

          return (
            <div key={req.requirement_id} className="document-card">
              <div className="document-card-header">
                <div>
                  <h3>{req.name}</h3>
                  <span className="document-kind">{req.is_conditional ? 'Conditionally required' : 'Required'}</span>
                </div>
                {res?.status === 'processed' ? (
                  <span className="badge success">Verified</span>
                ) : (
                  <button 
                    className="btn-secondary" 
                    onClick={() => handleUploadClick(req.requirement_id)}
                    disabled={isUploading || loading}
                  >
                    {isUploading ? 'Uploading...' : 'Upload PDF/Image'}
                  </button>
                )}
              </div>
              <p className="req-explanation">{req.explanation}</p>
              
              {res?.error && <p className="error-text">Extraction failed: {res.error}</p>}
              
              {res?.status === 'processed' && <p className="success-text">Your document has been received and processed.</p>}
            </div>
          );
        })}
      </div>

      {documents.length > 0 && <section className="panel">
        <h2>Your uploaded documents</h2>
        {documents.filter((document) => !document.replaced).map((document) => <div className="document-card" key={document.id}>
          <div className="document-card-header"><strong>{document.name}</strong><span className="badge">{document.status === 'processed' ? 'Processed' : document.status === 'processing' ? 'Processing' : document.status === 'error' ? 'Needs attention' : 'Uploaded'}</span></div>
          <button className="link-btn" onClick={() => api.viewDocument(document.id)}>View document</button>
          <button className="link-btn" onClick={() => api.getDocumentFields(document.id).then((fields) => setDocumentFields((current) => ({ ...current, [document.id]: fields }))).catch((err) => setError(err.message))}>View extracted information</button>
          {document.status !== 'replaced' && <label className="link-btn">Replace document<input type="file" hidden accept="application/pdf,image/jpeg,image/png,image/webp,image/tiff" onChange={async (event) => { const replacement = event.target.files?.[0]; if (!replacement) return; try { await api.replaceDocument(document.id, replacement); refreshDocuments(); } catch (err) { setError(err instanceof Error ? err.message : 'Unable to replace this document.'); } }} /></label>}
          {documentFields[document.id]?.length > 0 && <ul>{documentFields[document.id].map((field) => <li key={field.id}>{fieldLabel(field.key)}: {field.normalized_value || field.raw_value}</li>)}</ul>}
        </div>)}
      </section>}

      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        onChange={handleFileChange} 
        accept="application/pdf,image/jpeg,image/png,image/webp,image/tiff"
      />

      <div className="review-actions">
        <button 
          className="btn-primary" 
          disabled={!allUploaded || loading}
          onClick={handleSubmit}
        >
          {loading ? 'Processing...' : 'Submit to Underwriting →'}
        </button>
      </div>
    </div>
  );
}
