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

  return (
    <div className="page dashboard-page">
      <h1>Submission Queue</h1>
      <p className="subtitle">Applications available for underwriting review.</p>
      
      {error && <div className="error-box">{error}</div>}
      
      {loading ? (
        <p>Loading submissions...</p>
      ) : (
        <div className="submissions-grid">
          {submissions.length === 0 ? (
            <p className="empty">No submissions found.</p>
          ) : (
            <table className="table interactive-table">
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Product</th>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {submissions.map((sub) => (
                    <tr key={sub.id} onClick={() => navigate(`/underwriter/${sub.id}`)}>
                    <td>{sub.applicant_name}</td>
                    <td>{sub.product_name}</td>
                    <td>{new Date(sub.created_at).toLocaleDateString()}</td>
                    <td>{getStatusBadge(sub.status)}</td>
                    <td>
                      <button className="link-btn">Review</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

export default UnderwriterDashboard;
