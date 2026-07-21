/**
 * Axios API client for AI Research Assistant backend.
 * All HTTP calls go through this module.
 */
import axios, { AxiosInstance } from "axios";

const API_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

// ---- Type definitions ----

export interface UserResponse {
  id: string;
  email: string;
  username: string;
  created_at: string;
  is_active: boolean;
}

export interface DocumentResponse {
  id: string;
  user_id: string;
  filename: string;
  file_size: number;
  page_count: number | null;
  processing_status: "pending" | "processing" | "completed" | "failed";
  upload_timestamp: string;
  created_at: string;
}

export interface ChatSessionResponse {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  message_count: number | null;
}

export interface ChatMessageResponse {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Array<{
    filename?: string;
    page_number?: number;
    [key: string]: unknown;
  }> | null;
  tokens_used: number | null;
  created_at: string;
}

export interface SearchResult {
  chunk_id?: string;
  id?: string;
  text?: string;
  similarity?: number;
  page_number?: number;
  chunk_index?: number;
  semantic_score?: number;
  bm25_score?: number;
  rerank_score?: number;
  hybrid_score?: number;
  score?: number;
  source?: string;
}

// ---- Axios instance ----

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 60000,
});

// Attach JWT access token on every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// On 401 → try refresh → retry once → redirect to login
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refreshToken =
          typeof window !== "undefined"
            ? localStorage.getItem("refresh_token")
            : null;
        if (refreshToken) {
          const { data } = await axios.post(
            `${API_URL}/api/auth/refresh`,
            null,
            { headers: { "refresh-token": refreshToken } },
          );
          if (typeof window !== "undefined") {
            localStorage.setItem("access_token", data.access_token);
            if (data.refresh_token) {
              localStorage.setItem("refresh_token", data.refresh_token);
            }
          }
          original.headers = original.headers || {};
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        }
      } catch {
        // Refresh failed — clear tokens and redirect
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/auth/login";
        }
      }
    }
    return Promise.reject(error);
  },
);

// ---- API client methods ----

export const apiClient = {
  // ── Auth ──────────────────────────────────────────────────────────────────

  login: async (
    email: string,
    password: string,
  ): Promise<{
    user: { id: string; email: string; username: string };
    tokens: {
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
    };
    message: string;
  }> => {
    const { data } = await api.post("/api/auth/login", { email, password });
    return data;
  },

  register: async (
    email: string,
    username: string,
    password: string,
  ): Promise<{
    user: { id: string; email: string; username: string };
    tokens: {
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
    };
    message: string;
  }> => {
    const { data } = await api.post("/api/auth/register", {
      email,
      username,
      password,
    });
    return data;
  },

  logout: async (): Promise<void> => {
    await api.post("/api/auth/logout");
  },

  getCurrentUser: async (): Promise<UserResponse> => {
    const { data } = await api.get("/api/auth/me");
    return data as UserResponse;
  },

  // ── Documents ─────────────────────────────────────────────────────────────

  uploadDocument: async (file: File): Promise<DocumentResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post("/api/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data as DocumentResponse;
  },

  listDocuments: async (): Promise<DocumentResponse[]> => {
    const { data } = await api.get("/api/documents");
    // Backend returns { documents: [...], total: n }
    return (data.documents ?? data) as DocumentResponse[];
  },

  getDocument: async (documentId: string): Promise<DocumentResponse> => {
    const { data } = await api.get(`/api/documents/${documentId}`);
    return data as DocumentResponse;
  },

  deleteDocument: async (documentId: string): Promise<void> => {
    await api.delete(`/api/documents/${documentId}`);
  },

  // ── Chat ──────────────────────────────────────────────────────────────────

  createChatSession: async (
    documentIds: string[],
    title: string,
  ): Promise<ChatSessionResponse> => {
    const { data } = await api.post("/api/chat", {
      document_ids: documentIds,
      title,
    });
    return data as ChatSessionResponse;
  },

  listChatSessions: async (): Promise<ChatSessionResponse[]> => {
    const { data } = await api.get("/api/chat");
    // Backend returns { sessions: [...], total, skip, limit }
    return (data.sessions ?? data) as ChatSessionResponse[];
  },

  getChatHistory: async (
    sessionId: string,
  ): Promise<{
    messages: ChatMessageResponse[];
    session: ChatSessionResponse;
  }> => {
    const { data } = await api.get(`/api/chat/${sessionId}/history`);
    return data;
  },

  sendChatMessage: async (
    sessionId: string,
    content: string,
  ): Promise<ChatMessageResponse> => {
    const { data } = await api.post(`/api/chat/${sessionId}/message`, {
      content,
    });
    return data as ChatMessageResponse;
  },

  // ── Search ────────────────────────────────────────────────────────────────

  /** Semantic (vector) search */
  searchDocuments: async (
    documentId: string,
    query: string,
    topK = 5,
  ): Promise<SearchResult[]> => {
    const { data } = await api.post("/api/search/text", {
      document_id: documentId,
      query,
      top_k: topK,
    });
    return (data.results ?? []) as SearchResult[];
  },

  /** BM25 keyword search */
  bm25Search: async (
    documentId: string,
    query: string,
    topK = 5,
  ): Promise<{
    query: string;
    results: SearchResult[];
    total: number;
    search_type: string;
  }> => {
    const { data } = await api.post("/api/search/bm25", {
      document_id: documentId,
      query,
      top_k: topK,
    });
    return data;
  },

  /** Hybrid search (semantic + BM25 + reranking) */
  hybridSearch: async (
    documentId: string,
    query: string,
    topK = 5,
  ): Promise<{
    query: string;
    results: SearchResult[];
    total: number;
    search_time_ms: number;
  }> => {
    const { data } = await api.post("/api/search/hybrid", {
      document_id: documentId,
      query,
      top_k: topK,
    });
    return data;
  },

  // ── Voice ─────────────────────────────────────────────────────────────────

  /** Transcribe audio blob → text via Gemini (backend /api/voice/transcribe) */
  transcribeAudio: async (audioBlob: Blob): Promise<{ text: string }> => {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    const { data } = await api.post("/api/voice/transcribe", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 30000,
    });
    return data as { text: string };
  },
};
