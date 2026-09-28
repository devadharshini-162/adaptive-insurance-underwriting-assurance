import type { RequirementView } from '../services/api';

interface Props {
  requirements: RequirementView[];
  loading: boolean;
}

const statusIcon = (r: RequirementView) => (r.status === 'missing' ? '🔴' : '✅');

export default function RequirementsPanel({ requirements, loading }: Props) {
  if (loading) return <div className="panel"><p>Evaluating requirements…</p></div>;

  const unconditional = requirements.filter((r) => !r.is_conditional);
  const conditional   = requirements.filter((r) => r.is_conditional);

  return (
    <div className="panel requirements-panel">
      <h2>Document requirements</h2>

      {requirements.length === 0 && (
        <p className="empty">Answer questions above to see applicable requirements.</p>
      )}

      {unconditional.length > 0 && (
        <section>
          <h3>Required documents</h3>
          <ul>
            {unconditional.map((r) => (
              <li key={r.requirement_id} className="req-item req-unconditional">
                <span className="req-icon">{statusIcon(r)}</span>
                <div>
                  <strong>{r.name}</strong>
                  <p>{r.explanation}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {conditional.length > 0 && (
        <section>
          <h3>Conditionally Required</h3>
          <ul>
            {conditional.map((r) => (
              <li key={r.requirement_id} className="req-item req-conditional">
                <span className="req-icon">{statusIcon(r)}</span>
                <div>
                  <strong>{r.name}</strong>
                  <p className="req-explanation">⚡ {r.explanation}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Optional documents</h3>
        <p className="empty">No optional documents have been identified for this application.</p>
      </section>
    </div>
  );
}
