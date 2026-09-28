const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000';
const SESSION_KEY = 'insurance-assurance.session';

export type UserRole = 'customer' | 'underwriter';

export interface Session {
  token: string;
  role: UserRole;
}

function roleFromToken(token: string): UserRole | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(atob(base64.padEnd(base64.length + ((4 - base64.length % 4) % 4), '=')));
    return decoded.role === 'customer' || decoded.role === 'underwriter' ? decoded.role : null;
  } catch {
    return null;
  }
}

export function getStoredSession(): Session | null {
  try {
    const stored = localStorage.getItem(SESSION_KEY);
    if (!stored) return null;
    const session = JSON.parse(stored) as Session;
    return typeof session.token === 'string' && (session.role === 'customer' || session.role === 'underwriter') ? session : null;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function authorizationHeader(): HeadersInit {
  const session = getStoredSession();
  return session ? { Authorization: `Bearer ${session.token}` } : {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authorizationHeader(), ...options?.headers },
  });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('insurance-assurance:unauthorized'));
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
  section: string;
  options: string[];
}

export interface Submission {
  id: number;
  product_id: number;
  status: string;
  created_at: string;
}

export interface SubmissionListItem {
  id: number;
  product_id: number;
  product_name: string;
  applicant_name: string;
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

export interface ApplicationProfile {
  company_name?: string; business_type?: string; industry?: string; years_in_operation?: number;
  business_address?: string; city?: string; state?: string; country?: string; annual_revenue?: string;
  property_address?: string; property_type?: string; property_value?: string; ownership_type?: string;
  property_operations?: string; employee_count?: number;
}

export interface AdditionalRequest { id: number; type: 'information' | 'document'; document_name?: string; message: string; note?: string; status: string; }
export interface ApplicationState { submission: Pick<Submission, 'id' | 'product_id' | 'status'>; profile: ApplicationProfile; answers: Record<string, string>; requests: AdditionalRequest[]; decision_message?: string | null; }

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
  name: string;
  status: string;
  replaced: boolean;
}

export interface IngestResponse {
  document_id: number;
  status: string;
  error?: string;
  extracted_fields: Record<string, { raw: string; normalized: string }>;
}

// ── API calls ────────────────────────────────────────────────────────────────

export const api = {
  login: async (email: string, password: string): Promise<Session> => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!res.ok) {
      if (res.status === 401) window.dispatchEvent(new Event('insurance-assurance:unauthorized'));
      throw new Error('Invalid email or password.');
    }
    const token = (await res.json() as { access_token: string }).access_token;
    const role = roleFromToken(token);
    if (!role) throw new Error('The sign-in response was invalid. Please try again.');
    return { token, role };
  },

  getProducts: () => request<Product[]>('/api/products'),

  getQuestions: (productId: number) =>
    request<Question[]>(`/api/products/${productId}/questions`),

  createSubmission: (productId: number) =>
    request<Submission>('/api/submissions', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId }),
    }),

  evaluate: (productId: number, answers: Record<string, string>, contextData: ApplicationProfile = {}) =>
    request<EvaluateResponse>('/api/engine/evaluate', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId, current_answers: answers, context_data: contextData }),
    }),

  saveAnswers: (submissionId: number, answers: Record<string, string>) =>
    request<{ status: string; saved_count: number }>(`/api/submissions/${submissionId}/answers`, {
      method: 'PUT',
      body: JSON.stringify(answers),
    }),

  getApplication: (submissionId: number) => request<ApplicationState>(`/api/submissions/${submissionId}/application`),

  saveApplication: (submissionId: number, profile: ApplicationProfile) =>
    request<ApplicationProfile>(`/api/submissions/${submissionId}/application`, { method: 'PUT', body: JSON.stringify(profile) }),

  uploadDocument: async (submissionId: number, requirementId: number | null, file: File) => {
    const formData = new FormData();
    formData.append('submission_id', submissionId.toString());
    if (requirementId) formData.append('requirement_id', requirementId.toString());
    formData.append('file', file);

    const res = await fetch(`${BASE}/api/documents/upload`, {
      method: 'POST',
      headers: authorizationHeader(),
      body: formData,
    });
    if (!res.ok) {
      if (res.status === 401) window.dispatchEvent(new Event('insurance-assurance:unauthorized'));
      const body = await res.json().catch(() => null) as { detail?: string } | null;
      throw new Error(body?.detail || 'Unable to upload this document. Please try again.');
    }
    return res.json() as Promise<IngestResponse>;
  },

  getAllSubmissions: () => request<SubmissionListItem[]>('/api/submissions'),

  getMySubmissions: () => request<SubmissionListItem[]>('/api/submissions/mine'),

  generateIssues: (submissionId: number) =>
    request<{ status: string; issues_generated: number }>(`/api/submissions/${submissionId}/issues/generate`, {
      method: 'POST'
    }),

  getSubmissionDocuments: (submissionId: number) =>
    request<DocumentOut[]>(`/api/documents/submission/${submissionId}`),

  getDocumentFields: (documentId: number) => request<ExtractedFieldOut[]>(`/api/documents/${documentId}/fields`),

  viewDocument: async (documentId: number) => {
    const res = await fetch(`${BASE}/api/documents/${documentId}/content`, { headers: authorizationHeader() });
    if (!res.ok) throw new Error('Unable to open this document.');
    window.open(URL.createObjectURL(await res.blob()), '_blank', 'noopener,noreferrer');
  },

  replaceDocument: async (documentId: number, file: File) => {
    const formData = new FormData(); formData.append('file', file);
    const res = await fetch(`${BASE}/api/documents/${documentId}/replace`, { method: 'POST', headers: authorizationHeader(), body: formData });
    if (!res.ok) throw new Error('Unable to replace this document.');
    return res.json() as Promise<IngestResponse>;
  },

  createAdditionalRequest: (submissionId: number, payload: Omit<AdditionalRequest, 'id' | 'status'>) => request<{status: string}>(`/api/submissions/${submissionId}/requests`, { method: 'POST', body: JSON.stringify({ request_type: payload.type, document_name: payload.document_name, message: payload.message, note: payload.note }) }),

  uploadRequestedDocument: async (submissionId: number, requestId: number, file: File) => {
    const body = new FormData(); body.append('file', file);
    const res = await fetch(`${BASE}/api/documents/requested/${submissionId}/${requestId}`, { method: 'POST', headers: authorizationHeader(), body });
    if (!res.ok) throw new Error('Unable to upload the requested document.');
    return res.json() as Promise<IngestResponse>;
  },

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
