import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';

const SubmissionDetail: React.FC = () => {
  const { submissionId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState('');

  useEffect(() => {
    fetchData();
  }, [submissionId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const res = await api.getDashboardSummary(Number(submissionId));
      setData(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleIssueAction = async (issueId: number, action: string) => {
    try {
      await api.updateIssueStatus(Number(submissionId), issueId, action);
      await fetchData(); // Refresh data
    } catch (err: any) {
      alert(`Failed to update issue: ${err.message}`);
    }
  };

  const handleStatusUpdate = async (status: string) => {
    try {
      await api.updateSubmissionStatus(Number(submissionId), status, statusNote);
      await fetchData();
      setStatusNote('');
    } catch (err: any) {
      alert(`Failed to update status: ${err.message}`);
    }
  };

  if (loading) return <div className="page"><p>Loading submission details...</p></div>;
  if (error) return <div className="page"><div className="error-box">{error}</div></div>;
  if (!data) return null;

  const { submission, documents, issues, requirements, audit_trail, severity_counts } = data;

  return (
    <div className="page detail-page">
      <button className="link-btn breadcrumb" onClick={() => navigate('/dashboard')}>
        &larr; Back to Dashboard
      </button>

      {/* 1. Submission Overview */}
      <div className="dashboard-header panel">
        <div className="header-top">
          <div>
            <h1>Submission #{submission.id}: {submission.product_name}</h1>
            <p className="subtitle">Applicant: {submission.applicant} | Submitted: {new Date(submission.created_at).toLocaleString()}</p>
          </div>
          <div className={`status-badge status-${submission.status}`}>
            {submission.status.replace('_', ' ').toUpperCase()}
          </div>
        </div>
        
        <div className="overview-stats">
          <div className="stat-box">
            <span className="stat-label">Requirements</span>
            <span className="stat-value">{requirements.filter((r: any) => r.fulfilled).length} / {requirements.length}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Documents</span>
            <span className="stat-value">{documents.length} Uploaded</span>
          </div>
          <div className="stat-box issues-stat">
            <span className="stat-label">Critical Issues</span>
            <span className={`stat-value ${severity_counts.HIGH > 0 ? 'text-danger' : 'text-success'}`}>
              {severity_counts.HIGH} High
            </span>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="main-col">
          {/* 2. Underwriting Issues */}
          <section className="panel mb-4">
            <h2>Underwriting Issues</h2>
            {issues.length === 0 ? (
              <p className="empty">No issues found. Consistency looks good!</p>
            ) : (
              <div className="issues-list">
                {issues.map((i: any) => (
                  <div key={i.id} className={`issue-card severity-${i.details?.severity?.toLowerCase()}`}>
                    <div className="issue-header">
                      <span className={`badge badge-${i.details?.severity?.toLowerCase()}`}>
                        {i.details?.severity}
                      </span>
                      <strong>{i.description}</strong>
                      <span className="badge badge-secondary">{i.status}</span>
                    </div>
                    <div className="issue-body">
                      <p className="reason">{i.details?.reason}</p>
                      {i.details?.comparison_result === 'CONFLICT' && (
                        <div className="conflict-details">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Source</th>
                                <th>Raw Value</th>
                                <th>Normalized</th>
                              </tr>
                            </thead>
                            <tbody>
                              {i.details.sources?.map((src: string, idx: number) => (
                                <tr key={idx}>
                                  <td>{src}</td>
                                  <td>{i.details.raw_values[idx]}</td>
                                  <td>{i.details.normalized_values[idx]}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      
                      <p className="action-rec"><strong>Recommendation:</strong> {i.details?.recommended_action}</p>
                      
                    </div>
                    {i.status === 'open' && (
                      <div className="issue-actions">
                        <button className="btn-sm btn-success" onClick={() => handleIssueAction(i.id, 'resolve')}>Resolve</button>
                        <button className="btn-sm btn-outline" onClick={() => handleIssueAction(i.id, 'dismiss')}>Dismiss</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 5. Document Section */}
          <section className="panel">
            <h2>Documents & Extracted Evidence</h2>
            {documents.length === 0 ? (
              <p className="empty">No documents uploaded.</p>
            ) : (
              documents.map((d: any) => (
                <div key={d.id} className="document-card">
                  <div className="document-card-header">
                    <strong>{d.file_path}</strong>
                    <span className="badge badge-success">{d.status}</span>
                  </div>
                  {d.extracted_fields && d.extracted_fields.length > 0 ? (
                    <div className="extracted-fields">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Key</th>
                            <th>Raw Value</th>
                            <th>Normalized</th>
                          </tr>
                        </thead>
                        <tbody>
                          {d.extracted_fields.map((f: any) => (
                            <tr key={f.id}>
                              <td>{f.key}</td>
                              <td>{f.raw_value}</td>
                              <td>{f.normalized_value || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty">No fields extracted.</p>
                  )}
                </div>
              ))
            )}
          </section>
        </div>

        <div className="side-col">
          {/* 6. Underwriter Actions */}
          <section className="panel mb-4">
            <h2>Underwriter Decision</h2>
            <div className="action-form">
              <textarea 
                placeholder="Add note for audit trail..."
                value={statusNote}
                onChange={e => setStatusNote(e.target.value)}
                className="note-input"
              />
              <div className="decision-buttons">
                <button className="btn-primary w-100 mb-2" onClick={() => handleStatusUpdate('approved')}>Approve Submission</button>
                <button className="btn-secondary w-100 mb-2" onClick={() => handleStatusUpdate('info_requested')}>Request Info</button>
                <button className="btn-danger w-100" onClick={() => handleStatusUpdate('declined')}>Decline</button>
              </div>
            </div>
          </section>

          {/* 4. Requirements Checklist */}
          <section className="panel mb-4">
            <h2>Requirements Checklist</h2>
            <ul className="req-list">
              {requirements.map((r: any) => (
                <li key={r.requirement_id} className={`req-item ${r.fulfilled ? 'req-fulfilled' : 'req-missing'}`}>
                  <div className="req-icon">{r.fulfilled ? '✅' : '❌'}</div>
                  <div>
                    <strong>{r.name}</strong>
                    <p>{r.explanation}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Audit Trail */}
          <section className="panel audit-panel">
            <h2>Audit Log</h2>
            <div className="audit-timeline">
              {audit_trail.map((a: any) => (
                <div key={a.id} className="audit-event">
                  <div className="audit-time">{new Date(a.timestamp).toLocaleString()}</div>
                  <div className="audit-action">{a.action}</div>
                  {a.context_data?.note && <div className="audit-note">"{a.context_data.note}"</div>}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default SubmissionDetail;
