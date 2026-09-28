import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { SubmissionListItem } from '../services/api';

const statusLabels: Record<string, string> = {
  draft: 'Draft',
  under_review: 'Under review',
  info_requested: 'Information requested',
  approved: 'Approved',
  declined: 'Declined',
};

function statusLabel(status: string) {
  return statusLabels[status] ?? status.replaceAll('_', ' ');
}

export default function CustomerDashboard() {
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getMySubmissions()
      .then(setSubmissions)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unable to load your applications.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page dashboard-page">
      <div className="portal-heading">
        <div>
          <h1>My Applications</h1>
          <p className="subtitle">Track your insurance applications and continue drafts.</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/customer/new')}>New Application</button>
      </div>

      {error && <div className="error-box" role="alert">{error}</div>}
      {loading ? <p>Loading your applications…</p> : submissions.length === 0 ? (
        <section className="empty-state">
          <h2>No applications yet</h2>
          <p>Start a new application when you are ready.</p>
          <button className="btn-primary" onClick={() => navigate('/customer/new')}>Start an Application</button>
        </section>
      ) : (
        <div className="submission-list">
          {submissions.map((submission) => {
            const canContinue = submission.status === 'draft' || submission.status === 'info_requested';
            return (
              <article className="submission-card" key={submission.id}>
                <div>
                  <h2>{submission.product_name}</h2>
                  <p>{submission.applicant_name}</p>
                  <p className="submission-meta">Created {new Date(submission.created_at).toLocaleDateString()}</p>
                </div>
                <div className="submission-actions">
                  <span className={`badge status-${submission.status}`}>{submission.status === 'info_requested' ? 'Action Required' : statusLabel(submission.status)}</span>
                  {canContinue && <button className="btn-secondary" onClick={() => navigate(`/application/${submission.id}/${submission.status === 'info_requested' ? 'risk' : 'business'}`)}>
                    {submission.status === 'info_requested' ? 'Provide requested information' : 'Continue application'}
                  </button>}
                  {!canContinue && <button className="btn-secondary" onClick={() => navigate(`/review/${submission.id}`)}>View application</button>}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
