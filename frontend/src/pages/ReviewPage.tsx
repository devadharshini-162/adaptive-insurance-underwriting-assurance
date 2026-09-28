import { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import type { RequirementView, IngestResponse } from '../services/api';

export default function ReviewPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [requirements, setRequirements] = useState<RequirementView[]>((location.state?.requirements || []) as RequirementView[]);
  
  const [uploadingFor, setUploadingFor] = useState<number | null>(null);
  const [results, setResults] = useState<Record<number, IngestResponse>>({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!submissionId) return;
    
    // Fetch dashboard summary to get requirements and existing documents
    api.getDashboardSummary(Number(submissionId))
      .then((data) => {
        if (requirements.length === 0 && data.requirements) {
          setRequirements(data.requirements);
        }
        
        // Re-construct results from already uploaded documents
        if (data.documents) {
          const preResults: Record<number, any> = {};
          data.documents.forEach((d: any) => {
            if (d.requirement_id) {
              const extMap: Record<string, any> = {};
              d.extracted_fields?.forEach((f: any) => {
                extMap[f.key] = { raw: f.raw_value, normalized: f.normalized_value };
              });
              preResults[d.requirement_id] = { status: d.status, extracted_fields: extMap };
            }
          });
          setResults((prev) => ({ ...preResults, ...prev }));
        }
      })
      .catch((e) => setError(e.message));
  }, [submissionId]);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
    } finally {
        setUploadingFor(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const allUploaded = requirements.length > 0 && requirements.every(r => results[r.requirement_id]?.status === 'processed');

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');
      await api.generateIssues(Number(submissionId));
      navigate(`/dashboard/${submissionId}`);
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
        <span> / Upload Documents #{submissionId}</span>
      </nav>
      <h1>Document Upload & Extraction</h1>
      <p className="subtitle">Upload the following required documents for submission #{submissionId}.</p>
      
      {error && <div className="error-box">{error}</div>}

      <div className="requirements-list">
        {requirements.length === 0 && !loading && <p>No documents required. Please proceed.</p>}
        {requirements.map((req) => {
          const res = results[req.requirement_id];
          const isUploading = uploadingFor === req.requirement_id;

          return (
            <div key={req.requirement_id} className="document-card">
              <div className="document-card-header">
                <h3>{req.name}</h3>
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
              
              {res?.status === 'processed' && res.extracted_fields && (
                <div className="extracted-fields bg-light p-3 mt-3 rounded">
                  <h4>Automated Evidence Extraction</h4>
                  {Object.keys(res.extracted_fields).length === 0 ? (
                    <p className="text-muted">No canonical evidence fields detected in this document.</p>
                  ) : (
                    <table className="table table-sm">
                      <thead>
                        <tr>
                          <th>Field Name</th>
                          <th>Raw Extracted Value</th>
                          <th>Normalized Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(res.extracted_fields).map(([key, field]) => (
                          <tr key={key}>
                            <td><code>{key}</code></td>
                            <td>{field.raw}</td>
                            <td><strong>{field.normalized}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

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
