import { useEffect, useState, useRef, useMemo } from "react";
import { useRouter } from "next/router";
import { useAuthStore } from "@/lib/auth-store";
import {
  apiClient,
  ChatSessionResponse,
  ChatMessageResponse,
  DocumentResponse,
} from "@/lib/api";
import toast from "react-hot-toast";
import MarkdownIt from "markdown-it";
import {
  FiSend,
  FiPlus,
  FiArrowLeft,
  FiFileText,
  FiChevronDown,
  FiX,
  FiCheck,
  FiMessageSquare,
  FiBook,
  FiMic,
  FiMicOff,
} from "react-icons/fi";
import { HiSparkles } from "react-icons/hi2";

export default function ChatPage() {
  const router = useRouter();
  const { user, checkAuth } = useAuthStore();
  const [sessions, setSessions] = useState<ChatSessionResponse[]>([]);
  const [selectedSession, setSelectedSession] =
    useState<ChatSessionResponse | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showPdfModal, setShowPdfModal] = useState(false);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const md = useMemo(
    () =>
      new MarkdownIt({
        html: false,
        linkify: true,
        typographer: true,
        breaks: true,
      }),
    [],
  );

  useEffect(() => {
    const init = async () => {
      await checkAuth();
      if (!user) {
        router.push("/auth/login");
        return;
      }
      await loadData();
    };
    init();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const { document_id } = router.query;

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [sessionsData, docsData] = await Promise.all([
        apiClient.listChatSessions(),
        apiClient.listDocuments(),
      ]);
      setSessions(sessionsData);
      setDocuments(docsData);
      if (document_id && typeof document_id === "string") {
        setSelectedDocIds([document_id]);
      } else if (docsData.length > 0) {
        setSelectedDocIds([docsData[0].id]);
      }
      if (sessionsData.length > 0) {
        await selectSession(sessionsData[0]);
      }
    } catch {
      toast.error("Failed to load data");
    } finally {
      setIsLoading(false);
    }
  };

  const selectSession = async (session: ChatSessionResponse) => {
    try {
      setSelectedSession(session);
      const history = await apiClient.getChatHistory(session.id);
      setMessages(history.messages);
    } catch {
      toast.error("Failed to load chat history");
    }
  };

  const createNewSession = async (docIds?: string[]) => {
    const ids = docIds || selectedDocIds;
    if (ids.length === 0) {
      toast.error("Select at least one document");
      return;
    }
    try {
      const selectedNames = documents
        .filter((d) => ids.includes(d.id))
        .map((d) => d.filename.replace(".pdf", ""))
        .join(", ");
      const session = await apiClient.createChatSession(
        ids,
        `Chat – ${selectedNames} · ${new Date().toLocaleDateString()}`,
      );
      setSessions([session, ...sessions]);
      await selectSession(session);
      setShowPdfModal(false);
      toast.success("New chat session created");
    } catch {
      toast.error("Failed to create chat session");
    }
  };

  const handleSendMessage = async () => {
    if (!selectedSession || !messageInput.trim() || isSending) return;
    const content = messageInput;
    setMessageInput("");
    setIsSending(true);

    const tempUserMsg: ChatMessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: selectedSession.id,
      role: "user",
      content,
      citations: null,
      tokens_used: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const assistantMsg = await apiClient.sendChatMessage(
        selectedSession.id,
        content,
      );
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to send message");
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      setMessageInput(content);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const toggleDocSelection = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    );
  };

  // ── Voice recording ──────────────────────────────────────────────────────

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/ogg";
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        setIsTranscribing(true);
        try {
          const result = await apiClient.transcribeAudio(audioBlob);
          if (result.text) {
            setMessageInput(result.text);
            inputRef.current?.focus();
            toast.success("Voice transcribed!");
          }
        } catch {
          toast.error("Transcription failed — check GEMINI_API_KEY in .env");
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start();
      setIsRecording(true);
      toast("Recording… click mic again to stop", { icon: "🎙️" });
    } catch {
      toast.error(
        "Microphone access denied. Allow microphone in browser settings.",
      );
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const toggleRecording = () => {
    if (isRecording) stopRecording();
    else startRecording();
  };

  if (!user) return null;

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        background:
          "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* PDF Selector Modal */}
      {showPdfModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 50,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(8px)",
          }}
        >
          <div
            style={{
              background: "linear-gradient(145deg, #1e1b4b, #1a1a2e)",
              border: "1px solid rgba(139,92,246,0.3)",
              borderRadius: 20,
              padding: 32,
              width: 480,
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 25px 80px rgba(0,0,0,0.5)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 24,
              }}
            >
              <div>
                <h2
                  style={{
                    color: "#fff",
                    fontSize: 20,
                    fontWeight: 700,
                    margin: 0,
                  }}
                >
                  Choose Documents
                </h2>
                <p style={{ color: "#a78bfa", fontSize: 13, marginTop: 4 }}>
                  Select PDFs to include in this chat
                </p>
              </div>
              <button
                onClick={() => setShowPdfModal(false)}
                style={{
                  background: "rgba(255,255,255,0.08)",
                  border: "none",
                  borderRadius: 10,
                  width: 36,
                  height: 36,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  color: "#94a3b8",
                }}
              >
                <FiX size={18} />
              </button>
            </div>

            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 10,
                marginBottom: 24,
              }}
            >
              {documents.length === 0 ? (
                <div
                  style={{ textAlign: "center", padding: 40, color: "#64748b" }}
                >
                  <FiFileText
                    size={40}
                    style={{
                      margin: "0 auto 12px",
                      display: "block",
                      opacity: 0.5,
                    }}
                  />
                  <p>No documents uploaded yet</p>
                </div>
              ) : (
                documents.map((doc) => {
                  const selected = selectedDocIds.includes(doc.id);
                  return (
                    <button
                      key={doc.id}
                      onClick={() => toggleDocSelection(doc.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 14,
                        padding: "14px 16px",
                        background: selected
                          ? "rgba(139,92,246,0.2)"
                          : "rgba(255,255,255,0.04)",
                        border: selected
                          ? "1px solid rgba(139,92,246,0.6)"
                          : "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 12,
                        cursor: "pointer",
                        transition: "all 0.2s",
                        textAlign: "left",
                      }}
                    >
                      <div
                        style={{
                          width: 38,
                          height: 38,
                          borderRadius: 10,
                          background: selected
                            ? "linear-gradient(135deg,#7c3aed,#4f46e5)"
                            : "rgba(255,255,255,0.06)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          transition: "all 0.2s",
                        }}
                      >
                        <FiFileText
                          size={18}
                          color={selected ? "#fff" : "#64748b"}
                        />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p
                          style={{
                            color: "#e2e8f0",
                            fontSize: 14,
                            fontWeight: 600,
                            margin: 0,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {doc.filename}
                        </p>
                        <p
                          style={{
                            color: "#64748b",
                            fontSize: 12,
                            margin: "2px 0 0",
                          }}
                        >
                          {doc.page_count ? `${doc.page_count} pages` : "—"} ·{" "}
                          {doc.processing_status}
                        </p>
                      </div>
                      {selected && <FiCheck size={18} color="#a78bfa" />}
                    </button>
                  );
                })
              )}
            </div>

            <button
              onClick={() => createNewSession(selectedDocIds)}
              disabled={selectedDocIds.length === 0}
              style={{
                width: "100%",
                padding: "14px",
                background:
                  selectedDocIds.length === 0
                    ? "rgba(255,255,255,0.05)"
                    : "linear-gradient(135deg,#7c3aed,#4f46e5)",
                border: "none",
                borderRadius: 12,
                color: selectedDocIds.length === 0 ? "#475569" : "#fff",
                fontSize: 15,
                fontWeight: 600,
                cursor: selectedDocIds.length === 0 ? "not-allowed" : "pointer",
                transition: "all 0.2s",
              }}
            >
              Start Chat with {selectedDocIds.length} Document
              {selectedDocIds.length !== 1 ? "s" : ""}
            </button>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <div
        style={{
          width: 280,
          display: "flex",
          flexDirection: "column",
          background: "rgba(15,12,41,0.6)",
          backdropFilter: "blur(20px)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
          flexShrink: 0,
        }}
      >
        {/* Sidebar Header */}
        <div
          style={{
            padding: "20px 20px 16px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <button
            onClick={() => router.push("/dashboard")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 10,
              padding: "8px 14px",
              color: "#94a3b8",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              marginBottom: 16,
              transition: "all 0.2s",
              width: "100%",
            }}
          >
            <FiArrowLeft size={15} />
            Back to Dashboard
          </button>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 16,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <HiSparkles size={16} color="#fff" />
            </div>
            <div>
              <p
                style={{
                  color: "#e2e8f0",
                  fontSize: 14,
                  fontWeight: 700,
                  margin: 0,
                }}
              >
                AI Research Chat
              </p>
              <p style={{ color: "#64748b", fontSize: 11, margin: 0 }}>
                Powered by RAG
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowPdfModal(true)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
              border: "none",
              borderRadius: 12,
              padding: "11px 16px",
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 4px 20px rgba(124,58,237,0.4)",
              transition: "all 0.2s",
            }}
          >
            <FiPlus size={16} />
            New Chat
          </button>
        </div>

        {/* Session List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 12px" }}>
          {sessions.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "40px 20px",
                color: "#475569",
              }}
            >
              <FiMessageSquare
                size={32}
                style={{
                  margin: "0 auto 12px",
                  display: "block",
                  opacity: 0.4,
                }}
              />
              <p style={{ fontSize: 13 }}>No chats yet</p>
            </div>
          ) : (
            sessions.map((session) => {
              const active = selectedSession?.id === session.id;
              return (
                <button
                  key={session.id}
                  onClick={() => selectSession(session)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: "12px 14px",
                    borderRadius: 12,
                    border: active
                      ? "1px solid rgba(139,92,246,0.4)"
                      : "1px solid transparent",
                    background: active
                      ? "rgba(139,92,246,0.15)"
                      : "transparent",
                    cursor: "pointer",
                    marginBottom: 4,
                    transition: "all 0.2s",
                  }}
                >
                  <p
                    style={{
                      color: active ? "#c4b5fd" : "#94a3b8",
                      fontSize: 13,
                      fontWeight: 600,
                      margin: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {session.title || "Untitled Chat"}
                  </p>
                  <p
                    style={{
                      color: "#475569",
                      fontSize: 11,
                      margin: "3px 0 0",
                    }}
                  >
                    {session.message_count ?? 0} messages
                  </p>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 20px",
            borderTop: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <p style={{ color: "#475569", fontSize: 11, margin: 0 }}>
            Signed in as
          </p>
          <p
            style={{
              color: "#7c3aed",
              fontSize: 12,
              fontWeight: 600,
              margin: "2px 0 0",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {user.email}
          </p>
        </div>
      </div>

      {/* Main Chat Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        {selectedSession ? (
          <>
            {/* Chat Header */}
            <div
              style={{
                padding: "18px 28px",
                borderBottom: "1px solid rgba(255,255,255,0.06)",
                background: "rgba(15,12,41,0.4)",
                backdropFilter: "blur(20px)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 12,
                    background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <FiBook size={18} color="#fff" />
                </div>
                <div>
                  <h2
                    style={{
                      color: "#e2e8f0",
                      fontSize: 16,
                      fontWeight: 700,
                      margin: 0,
                    }}
                  >
                    {selectedSession.title || "Chat"}
                  </h2>
                  <p style={{ color: "#64748b", fontSize: 12, margin: 0 }}>
                    {messages.length} messages
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowPdfModal(true)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background: "rgba(139,92,246,0.1)",
                  border: "1px solid rgba(139,92,246,0.3)",
                  borderRadius: 10,
                  padding: "8px 16px",
                  color: "#a78bfa",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <FiFileText size={14} />
                Choose PDFs
                <FiChevronDown size={13} />
              </button>
            </div>

            {/* Messages */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "24px 28px",
                display: "flex",
                flexDirection: "column",
                gap: 20,
              }}
            >
              {isLoading ? (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    height: "100%",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: "50%",
                      border: "3px solid rgba(139,92,246,0.3)",
                      borderTopColor: "#7c3aed",
                      animation: "spin 1s linear infinite",
                    }}
                  />
                  <p style={{ color: "#64748b", fontSize: 14 }}>
                    Loading messages...
                  </p>
                </div>
              ) : messages.length === 0 ? (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    height: "100%",
                    flexDirection: "column",
                    gap: 16,
                  }}
                >
                  <div
                    style={{
                      width: 72,
                      height: 72,
                      borderRadius: 20,
                      background:
                        "linear-gradient(135deg,rgba(124,58,237,0.2),rgba(79,70,229,0.2))",
                      border: "1px solid rgba(139,92,246,0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <HiSparkles size={32} color="#7c3aed" />
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <p
                      style={{
                        color: "#e2e8f0",
                        fontSize: 18,
                        fontWeight: 700,
                        margin: "0 0 8px",
                      }}
                    >
                      Ask anything about your document
                    </p>
                    <p style={{ color: "#64748b", fontSize: 14 }}>
                      Type a question below to get AI-powered answers with
                      citations
                    </p>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 10,
                      flexWrap: "wrap",
                      justifyContent: "center",
                      maxWidth: 520,
                    }}
                  >
                    {[
                      "What is the main topic?",
                      "Summarize key points",
                      "What are the conclusions?",
                    ].map((s) => (
                      <button
                        key={s}
                        onClick={() => {
                          setMessageInput(s);
                          inputRef.current?.focus();
                        }}
                        style={{
                          background: "rgba(139,92,246,0.1)",
                          border: "1px solid rgba(139,92,246,0.25)",
                          borderRadius: 20,
                          padding: "8px 16px",
                          color: "#a78bfa",
                          fontSize: 13,
                          cursor: "pointer",
                          transition: "all 0.2s",
                        }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      justifyContent:
                        msg.role === "user" ? "flex-end" : "flex-start",
                      gap: 12,
                    }}
                  >
                    {msg.role === "assistant" && (
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 10,
                          background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          marginTop: 4,
                        }}
                      >
                        <HiSparkles size={16} color="#fff" />
                      </div>
                    )}
                    <div
                      style={{
                        maxWidth: "70%",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      <div
                        style={{
                          padding: "14px 18px",
                          borderRadius:
                            msg.role === "user"
                              ? "18px 18px 4px 18px"
                              : "18px 18px 18px 4px",
                          background:
                            msg.role === "user"
                              ? "linear-gradient(135deg,#7c3aed,#4f46e5)"
                              : "rgba(255,255,255,0.06)",
                          border:
                            msg.role === "user"
                              ? "none"
                              : "1px solid rgba(255,255,255,0.08)",
                          boxShadow:
                            msg.role === "user"
                              ? "0 4px 20px rgba(124,58,237,0.3)"
                              : "none",
                        }}
                      >
                        {msg.role === "assistant" ? (
                          <div
                            className="ai-markdown"
                            dangerouslySetInnerHTML={{
                              __html: md.render(msg.content),
                            }}
                            style={{
                              color: "#e2e8f0",
                              fontSize: 14,
                              lineHeight: 1.75,
                              margin: 0,
                            }}
                          />
                        ) : (
                          <p
                            style={{
                              color: "#fff",
                              fontSize: 14,
                              lineHeight: 1.65,
                              margin: 0,
                              whiteSpace: "pre-wrap",
                              textAlign: "left",
                            }}
                          >
                            {msg.content}
                          </p>
                        )}
                      </div>
                      {msg.citations && msg.citations.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: 6,
                            paddingLeft: 4,
                          }}
                        >
                          {msg.citations.map((cite, idx) => (
                            <span
                              key={idx}
                              style={{
                                background: "rgba(139,92,246,0.12)",
                                border: "1px solid rgba(139,92,246,0.25)",
                                borderRadius: 20,
                                padding: "3px 10px",
                                color: "#a78bfa",
                                fontSize: 11,
                                fontWeight: 600,
                              }}
                            >
                              [{idx + 1}] p.{cite.page_number ?? "?"}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    {msg.role === "user" && (
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 10,
                          background: "rgba(255,255,255,0.08)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          marginTop: 4,
                          color: "#94a3b8",
                          fontSize: 14,
                          fontWeight: 700,
                        }}
                      >
                        {user.email[0].toUpperCase()}
                      </div>
                    )}
                  </div>
                ))
              )}
              {isSending && (
                <div style={{ display: "flex", gap: 12 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 10,
                      background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <HiSparkles size={16} color="#fff" />
                  </div>
                  <div
                    style={{
                      padding: "14px 18px",
                      borderRadius: "18px 18px 18px 4px",
                      background: "rgba(255,255,255,0.06)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: "#7c3aed",
                        animation: "pulse 1s ease-in-out infinite",
                      }}
                    />
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: "#7c3aed",
                        animation: "pulse 1s ease-in-out 0.2s infinite",
                      }}
                    />
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: "#7c3aed",
                        animation: "pulse 1s ease-in-out 0.4s infinite",
                      }}
                    />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div
              style={{
                padding: "16px 28px 20px",
                borderTop: "1px solid rgba(255,255,255,0.06)",
                background: "rgba(15,12,41,0.4)",
                backdropFilter: "blur(20px)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "flex-end",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(139,92,246,0.2)",
                  borderRadius: 16,
                  padding: "12px 14px",
                  transition: "border-color 0.2s",
                }}
              >
                <textarea
                  ref={inputRef}
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a question about your document… (Enter to send, Shift+Enter for newline)"
                  disabled={isSending}
                  rows={1}
                  style={{
                    flex: 1,
                    background: "transparent",
                    border: "none",
                    outline: "none",
                    color: "#e2e8f0",
                    fontSize: 14,
                    lineHeight: 1.6,
                    resize: "none",
                    fontFamily: "inherit",
                    maxHeight: 120,
                    overflowY: "auto",
                  }}
                  onInput={(e) => {
                    const t = e.target as HTMLTextAreaElement;
                    t.style.height = "auto";
                    t.style.height = Math.min(t.scrollHeight, 120) + "px";
                  }}
                />
                {/* Mic button */}
                <button
                  onClick={toggleRecording}
                  disabled={isSending || isTranscribing}
                  title={isRecording ? "Stop recording" : "Start voice input"}
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 12,
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor:
                      isSending || isTranscribing ? "not-allowed" : "pointer",
                    transition: "all 0.2s",
                    flexShrink: 0,
                    background: isRecording
                      ? "linear-gradient(135deg,#dc2626,#b91c1c)"
                      : isTranscribing
                        ? "rgba(255,255,255,0.05)"
                        : "rgba(255,255,255,0.08)",
                    boxShadow: isRecording
                      ? "0 4px 16px rgba(220,38,38,0.5)"
                      : "none",
                    animation: isRecording
                      ? "pulse-ring 1.5s ease-in-out infinite"
                      : "none",
                  }}
                >
                  {isTranscribing ? (
                    <div
                      style={{
                        width: 16,
                        height: 16,
                        borderRadius: "50%",
                        border: "2px solid rgba(255,255,255,0.3)",
                        borderTopColor: "#fff",
                        animation: "spin 0.8s linear infinite",
                      }}
                    />
                  ) : isRecording ? (
                    <FiMicOff size={18} color="#fff" />
                  ) : (
                    <FiMic size={18} color="#94a3b8" />
                  )}
                </button>

                {/* Send button */}
                <button
                  onClick={handleSendMessage}
                  disabled={isSending || !messageInput.trim()}
                  style={{
                    width: 42,
                    height: 42,
                    borderRadius: 12,
                    background:
                      isSending || !messageInput.trim()
                        ? "rgba(255,255,255,0.05)"
                        : "linear-gradient(135deg,#7c3aed,#4f46e5)",
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor:
                      isSending || !messageInput.trim()
                        ? "not-allowed"
                        : "pointer",
                    transition: "all 0.2s",
                    boxShadow:
                      isSending || !messageInput.trim()
                        ? "none"
                        : "0 4px 16px rgba(124,58,237,0.4)",
                    flexShrink: 0,
                  }}
                >
                  <FiSend
                    size={18}
                    color={
                      isSending || !messageInput.trim() ? "#475569" : "#fff"
                    }
                  />
                </button>
              </div>
              <p
                style={{
                  color: "#475569",
                  fontSize: 11,
                  textAlign: "center",
                  marginTop: 10,
                }}
              >
                AI responses are based on your uploaded documents via semantic
                search
              </p>
            </div>
          </>
        ) : (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              gap: 24,
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: 22,
                background:
                  "linear-gradient(135deg,rgba(124,58,237,0.2),rgba(79,70,229,0.2))",
                border: "1px solid rgba(139,92,246,0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <HiSparkles size={36} color="#7c3aed" />
            </div>
            <div style={{ textAlign: "center" }}>
              <h2
                style={{
                  color: "#e2e8f0",
                  fontSize: 24,
                  fontWeight: 800,
                  margin: "0 0 10px",
                  fontFamily: "'Plus Jakarta Sans',sans-serif",
                }}
              >
                Start a Conversation
              </h2>
              <p style={{ color: "#64748b", fontSize: 15, maxWidth: 400 }}>
                {documents.length === 0
                  ? "Upload a PDF document first, then come back to chat."
                  : 'Click "New Chat" to select your documents and begin.'}
              </p>
            </div>
            {documents.length > 0 ? (
              <button
                onClick={() => setShowPdfModal(true)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  background: "linear-gradient(135deg,#7c3aed,#4f46e5)",
                  border: "none",
                  borderRadius: 14,
                  padding: "14px 28px",
                  color: "#fff",
                  fontSize: 15,
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 8px 30px rgba(124,58,237,0.4)",
                  transition: "all 0.2s",
                }}
              >
                <FiPlus size={18} /> Start New Chat
              </button>
            ) : (
              <button
                onClick={() => router.push("/dashboard")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 14,
                  padding: "14px 28px",
                  color: "#94a3b8",
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <FiArrowLeft size={16} /> Go to Dashboard
              </button>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:0.3; transform:scale(0.8); } 50% { opacity:1; transform:scale(1); } }
        .ai-markdown p { margin: 0 0 10px; text-align: left; }
        .ai-markdown p:last-child { margin-bottom: 0; }
        .ai-markdown ul, .ai-markdown ol { padding-left: 20px; margin: 8px 0 12px; }
        .ai-markdown li { margin-bottom: 6px; line-height: 1.7; }
        .ai-markdown strong { color: #c4b5fd; font-weight: 700; }
        .ai-markdown em { color: #a78bfa; font-style: italic; }
        .ai-markdown h1, .ai-markdown h2, .ai-markdown h3 { color: #c4b5fd; font-weight: 700; margin: 14px 0 8px; line-height: 1.4; }
        .ai-markdown h1 { font-size: 18px; }
        .ai-markdown h2 { font-size: 16px; }
        .ai-markdown h3 { font-size: 15px; }
        .ai-markdown code { background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.25); border-radius: 4px; padding: 1px 6px; font-size: 12px; color: #c4b5fd; font-family: 'Fira Code', monospace; }
        .ai-markdown pre { background: rgba(0,0,0,0.3); border: 1px solid rgba(139,92,246,0.2); border-radius: 10px; padding: 14px; margin: 10px 0; overflow-x: auto; }
        .ai-markdown pre code { background: transparent; border: none; padding: 0; font-size: 13px; }
        .ai-markdown blockquote { border-left: 3px solid #7c3aed; padding-left: 14px; margin: 10px 0; color: #94a3b8; font-style: italic; }
        .ai-markdown a { color: #818cf8; text-decoration: underline; }
        .ai-markdown hr { border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 14px 0; }
      `}</style>
    </div>
  );
}
