import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { Question, RequirementView } from '../services/api';
import RequirementsPanel from '../components/RequirementsPanel';

export default function Questionnaire() {
  const { submissionId, productId } = useParams<{ submissionId: string; productId: string }>();
  const navigate = useNavigate();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [requirements, setRequirements] = useState<RequirementView[]>([]);
  const [loadingQ, setLoadingQ] = useState(true);
  const [loadingEval, setLoadingEval] = useState(false);
  const [error, setError] = useState('');

  const pId = Number(productId);

  // Initial load: fetch questions, existing answers, and run evaluations
  useEffect(() => {
    if (!pId || !submissionId) return;

    let pre_answers: Record<string, string> = {};

    api.getQuestions(pId)
    .then((qs) => {
      setQuestions(qs);
      return api.evaluate(pId, pre_answers);
    })
    .then((res) => setRequirements(res.requirements))
    .catch((e) => setError(e.message))
    .finally(() => setLoadingQ(false));
  }, [pId, submissionId]);

  // Re-evaluate whenever answers change
  const runEval = useCallback(async (currentAnswers: Record<string, string>) => {
    setLoadingEval(true);
    setError('');
    try {
      const res = await api.evaluate(pId, currentAnswers);
      setRequirements(res.requirements);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingEval(false);
    }
  }, [pId]);

  function handleChange(questionId: number, value: string) {
    const updated = { ...answers, [String(questionId)]: value };
    setAnswers(updated);
    runEval(updated);
  }

  function renderField(q: Question) {
    const val = answers[String(q.id)] ?? '';

    if (q.field_type === 'yesno') {
      return (
        <select
          id={`q-${q.id}`}
          value={val}
          onChange={(e) => handleChange(q.id, e.target.value)}
        >
          <option value="">— select —</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      );
    }

    if (q.field_type === 'number') {
      return (
        <input
          id={`q-${q.id}`}
          type="number"
          value={val}
          placeholder="Enter a value"
          onChange={(e) => handleChange(q.id, e.target.value)}
        />
      );
    }

    // Default: text
    return (
      <input
        id={`q-${q.id}`}
        type="text"
        value={val}
        placeholder="Enter your answer"
        onChange={(e) => handleChange(q.id, e.target.value)}
      />
    );
  }

  const allAnswered = questions.every((q) => q.is_required ? !!answers[String(q.id)] : true);

  if (loadingQ) return <div className="page"><p>Loading questionnaire…</p></div>;

  const handleReviewSubmit = async () => {
    try {
      setLoadingEval(true); // Treat as general loading
      if (submissionId) {
        await api.saveAnswers(Number(submissionId), answers);
      }
      navigate(`/review/${submissionId}`, { state: { requirements } });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!submissionId) setLoadingEval(false);
    }
  };

  return (
    <div className="page two-col">
      {/* Left: questions */}
      <div className="col-questions">
        <nav className="breadcrumb">
          <button className="link-btn" onClick={() => navigate('/customer')}>← Back</button>
          <span> / Questionnaire</span>
        </nav>
        <h1>Adaptive Questionnaire</h1>
        <p className="subtitle">Answer all fields. Requirements update in real-time.</p>

        {error && <div className="error-box">{error}</div>}

        <form className="question-form" onSubmit={(e) => e.preventDefault()}>
          {questions.map((q) => (
            <div key={q.id} className="field-group">
              <label htmlFor={`q-${q.id}`}>
                {q.text}
                {q.is_required && <span className="required-star">*</span>}
              </label>
              {renderField(q)}
            </div>
          ))}
        </form>

        <button
          className="btn-primary"
          disabled={!allAnswered || loadingEval}
          onClick={handleReviewSubmit}
        >
          {loadingEval ? 'Saving...' : 'Review Submission →'}
        </button>
      </div>

      {/* Right: requirements panel */}
      <div className="col-requirements">
        <RequirementsPanel requirements={requirements} loading={loadingEval} />
      </div>
    </div>
  );
}
