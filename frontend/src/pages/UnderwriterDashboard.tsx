import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { SubmissionListItem } from '../services/api';

const UnderwriterDashboard: React.FC = () => {
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchSubmissions() {
      try {
        const data = await api.getAllSubmissions();
        setSubmissions(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchSubmissions();
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved': return <span className="badge badge-success">Approved</span>;
      case 'declined': return <span className="badge badge-error">Declined</span>;
      case 'under_review': return <span className="badge badge-warning">Under Review</span>;
      case 'info_requested': return <span className="badge badge-info">Info Requested</span>;
      default: return <span className="badge badge-secondary">{status}</span>;
    }
  };

  const activeSubmissions = submissions.filter((submission) => submission.status === 'under_review' || submission.status === 'info_requested');
  const completedSubmissions = submissions.filter((submission) => submission.status === 'approved' || submission.status === 'declined');
  const renderTable = (rows: SubmissionListItem[], emptyMessage: string) => rows.length === 0 ? <p className="empty">{emptyMessage}</p> : (
    <table className="queue-table interactive-table">
      <thead><tr><th>Applicant</th><th>Product</th><th>Insurer</th><th>Underwriter</th><th>Created</th><th>Status</th><th>Action</th></tr></thead>
      <tbody>{rows.map((sub) => <tr key={sub.id} onClick={() => navigate(`/underwriter/${sub.id}`)}><td data-label="Applicant">{sub.applicant_name}</td><td data-label="Product">{sub.product_name}</td><td data-label="Insurer">{sub.insurance_company_name || 'Unassigned legacy application'}</td><td data-label="Underwriter">{sub.assigned_underwriter_name || 'Queue assignment'}</td><td data-label="Created">{new Date(sub.created_at).toLocaleDateString()}</td><td data-label="Status">{getStatusBadge(sub.status)}</td><td data-label="Action"><button className="link-btn">Review</button></td></tr>)}</tbody>
    </table>
  );

  return (
    <div className="page dashboard-page">
      <h1>Submission Queue</h1>
      <p className="subtitle">Applications available for underwriting review.</p>
      
      {error && <div className="error-box">{error}</div>}
      
      {loading ? (
        <p>Loading submissions...</p>
      ) : (
        <div className="submissions-grid">
          <><section className="panel queue-section"><div className="issue-section-heading"><div><h2>Active review work</h2><p className="subtitle">Applications awaiting assessment or additional information.</p></div><span className="badge badge-warning">{activeSubmissions.length} active</span></div>{renderTable(activeSubmissions, 'No active applications require review.')}</section>{completedSubmissions.length > 0 && <details className="completed-issues"><summary>Completed decisions ({completedSubmissions.length})</summary>{renderTable(completedSubmissions, 'No completed decisions.')}</details>}</>
        </div>
      )}
    </div>
  );
};

export default UnderwriterDashboard;
