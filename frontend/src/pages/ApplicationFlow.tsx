import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../services/api';
import type { ApplicationProfile, Question, RequirementView } from '../services/api';

const steps = ['business', 'property', 'risk', 'questions'];
const titles: Record<string, string> = { business: 'Business information', property: 'Property information', risk: 'Risk information', questions: 'Additional questions' };

const fields: Record<string, { key: keyof ApplicationProfile; label: string; type?: string; options?: string[] }[]> = {
  business: [
    { key: 'company_name', label: 'Company name' }, { key: 'business_type', label: 'Business type' }, { key: 'industry', label: 'Industry' },
    { key: 'years_in_operation', label: 'Years in operation', type: 'number' }, { key: 'business_address', label: 'Business address' },
    { key: 'city', label: 'City' }, { key: 'state', label: 'State' }, { key: 'country', label: 'Country' }, { key: 'annual_revenue', label: 'Annual revenue', type: 'number' },
  ],
  property: [
    { key: 'property_address', label: 'Property address' }, { key: 'property_type', label: 'Property type' }, { key: 'property_value', label: 'Approximate property value', type: 'number' },
    { key: 'ownership_type', label: 'Do you own or lease the property?', options: ['Owned', 'Leased'] }, { key: 'property_operations', label: 'What is kept or operated at the property?' }, { key: 'employee_count', label: 'Number of employees', type: 'number' },
  ],
};

export default function ApplicationFlow() {
  const { submissionId, step = 'business' } = useParams();
  const navigate = useNavigate();
  const id = Number(submissionId);
  const [profile, setProfile] = useState<ApplicationProfile>({});
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [questions, setQuestions] = useState<Question[]>([]);
  const [requirements, setRequirements] = useState<RequirementView[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    const state = await api.getApplication(id);
    setProfile(state.profile); setAnswers(state.answers);
    const evaluated = await api.evaluate(state.submission.product_id, state.answers, state.profile);
    setQuestions(evaluated.applicable_questions); setRequirements(evaluated.requirements);
  }
  useEffect(() => { refresh().catch((e) => setError(e.message)).finally(() => setLoading(false)); }, [id]);

  const go = (next: string) => navigate(`/application/${id}/${next}`);
  const updateProfile = (key: keyof ApplicationProfile, value: string) => setProfile((previous) => ({ ...previous, [key]: value }));
  const updateAnswer = async (question: Question, value: string) => {
    const next = { ...answers, [String(question.id)]: value };
    setAnswers(next);
    try {
      // Save each answer as it is made so a refresh or a trip back does not
      // discard completed questionnaire work.
      await api.saveAnswers(id, next);
      const state = await api.getApplication(id);
      const evaluated = await api.evaluate(state.submission.product_id, next, profile);
      setQuestions(evaluated.applicable_questions); setRequirements(evaluated.requirements);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unable to save this answer.');
    }
  };

  async function continueFlow() {
    setSaving(true); setError('');
    try {
      if (step === 'business' || step === 'property') await api.saveApplication(id, profile);
      if (step === 'risk' || step === 'questions') await api.saveAnswers(id, answers);
      const index = steps.indexOf(step);
      if (index < steps.length - 1) go(steps[index + 1]);
      else navigate(`/review/${id}`, { state: { requirements } });
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Unable to save your application.'); }
    finally { setSaving(false); }
  }
  const currentFields = fields[step] || [];
  const visibleQuestions = questions.filter((question) => step === 'risk' ? question.section === 'risk' : step === 'questions' ? question.section !== 'risk' : false);
  const isComplete = currentFields.length > 0
    ? currentFields.every((field) => profile[field.key] !== undefined && profile[field.key] !== '')
    : visibleQuestions.every((q) => !q.is_required || !!answers[String(q.id)]);
  if (loading) return <div className="page"><p>Loading your application…</p></div>;

  return <div className="page">
    <nav className="breadcrumb"><button className="link-btn" onClick={() => steps.indexOf(step) ? go(steps[steps.indexOf(step) - 1]) : navigate('/customer')}>← Back</button><span> / {steps.indexOf(step) + 1} of {steps.length}</span></nav>
    <h1>{titles[step] || 'Application'}</h1>
    <p className="subtitle">Your progress is saved when you continue.</p>
    {error && <div className="error-box">{error}</div>}
    <div className="question-form">
      {currentFields.map((field) => <div className="field-group" key={field.key}><label>{field.label}</label>{field.options ? <select value={String(profile[field.key] || '')} onChange={(e) => updateProfile(field.key, e.target.value)}><option value="">Select an option</option>{field.options.map((option) => <option key={option}>{option}</option>)}</select> : <input type={field.type || 'text'} value={String(profile[field.key] || '')} onChange={(e) => updateProfile(field.key, e.target.value)} />}</div>)}
      {visibleQuestions.map((question) => <div className="field-group" key={question.id}><label>{question.text}{question.is_required && <span className="required-star">*</span>}</label>{question.field_type === 'yesno' || question.field_type === 'select' ? <select value={answers[String(question.id)] || ''} onChange={(e) => updateAnswer(question, e.target.value)}><option value="">Select an option</option>{(question.options.length ? question.options : ['yes', 'no']).map((option) => <option key={option} value={option}>{option}</option>)}</select> : <input type={question.field_type === 'number' ? 'number' : 'text'} value={answers[String(question.id)] || ''} onChange={(e) => updateAnswer(question, e.target.value)} />}</div>)}
    </div>
    <button className="btn-primary" disabled={!isComplete || saving} onClick={continueFlow}>{saving ? 'Saving…' : step === 'questions' ? 'Continue to documents' : 'Continue'}</button>
  </div>;
}
