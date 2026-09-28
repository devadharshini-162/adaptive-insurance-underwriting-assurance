const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface Product {
  id: number;
  name: string;
  description: string;
}

export interface Question {
  id: number;
  text: string;
  field_type: string;
  is_required: boolean;
}

export interface Submission {
  id: number;
  product_id: number;
  status: string;
  created_at: string;
}

export interface RequirementView {
  requirement_id: number;
  name: string;
  explanation: string;
  is_conditional: boolean;
  status: string;
}

export interface EvaluateResponse {
  applicable_questions: Question[];
  requirements: RequirementView[];
}

export interface ExtractedFieldOut {
  id: number;
  key: string;
  raw_value: string;
  normalized_value: string | null;
}

export interface DocumentOut {
  id: number;
  submission_id: number;
  requirement_id: number | null;
  file_path: string;
  status: string;
}

export interface IngestResponse {
  document_id: number;
  status: string;
  error?: string;
  extracted_fields: Record<string, { raw: string; normalized: string }>;
}

// ── API calls ────────────────────────────────────────────────────────────────

export const api = {
  getProducts: () => request<Product[]>('/api/products'),

  getQuestions: (productId: number) =>
    request<Question[]>(`/api/products/${productId}/questions`),

  createSubmission: (productId: number) =>
    request<Submission>('/api/submissions', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId }),
    }),

  evaluate: (productId: number, answers: Record<string, string>) =>
    request<EvaluateResponse>('/api/engine/evaluate', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId, current_answers: answers }),
    }),

  saveAnswers: (submissionId: number, answers: Record<string, string>) =>
    request<{ status: string; saved_count: number }>(`/api/submissions/${submissionId}/answers`, {
      method: 'PUT',
      body: JSON.stringify(answers),
    }),

  uploadDocument: async (submissionId: number, requirementId: number | null, file: File) => {
    const formData = new FormData();
    formData.append('submission_id', submissionId.toString());
    if (requirementId) formData.append('requirement_id', requirementId.toString());
    formData.append('file', file);

    const res = await fetch(`${BASE}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    return res.json() as Promise<IngestResponse>;
  },

  getAllSubmissions: () => request<Submission[]>('/api/submissions'),

  generateIssues: (submissionId: number) =>
    request<{ status: string; issues_generated: number }>(`/api/submissions/${submissionId}/issues/generate`, {
      method: 'POST'
    }),

  getSubmissionDocuments: (submissionId: number) =>
    request<DocumentOut[]>(`/api/documents/submission/${submissionId}`),

  getDashboardSummary: (submissionId: number) => request<any>(`/api/submissions/${submissionId}/dashboard`),

  updateIssueStatus: (submissionId: number, issueId: number, action: string, note?: string) => 
    request<{status: string, issue_status: string}>(`/api/submissions/${submissionId}/issues/${issueId}`, {
      method: 'PUT',
      body: JSON.stringify({ action, note })
    }),
    
  updateSubmissionStatus: (submissionId: number, status: string, note?: string) =>
    request<{status: string, submission_status: string}>(`/api/submissions/${submissionId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, note })
    }),
};
