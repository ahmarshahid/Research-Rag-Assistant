import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/router";
import { useAuthStore } from "@/lib/auth-store";
import {
  apiClient,
  ChatSessionResponse,
  ChatMessageResponse,
  DocumentResponse,
} from "@/lib/api";
import toast from "react-hot-toast";
import { FiSend, FiPlus } from "react-icons/fi";

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [sessionsData, docsData] = await Promise.all([
        apiClient.listChatSessions(),
        apiClient.listDocuments(),
      ]);
      setSessions(sessionsData);
      setDocuments(docsData);

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

  const createNewSession = async () => {
    if (documents.length === 0) {
      toast.error("Upload a document first");
      return;
    }

    try {
      const session = await apiClient.createChatSession(
        [documents[0].id],
        `Chat - ${new Date().toLocaleDateString()}`,
      );
      setSessions([session, ...sessions]);
      await selectSession(session);
      toast.success("Chat session created");
    } catch {
      toast.error("Failed to create chat session");
    }
  };

  const handleSendMessage = async () => {
    if (!selectedSession || !messageInput.trim()) return;

    const content = messageInput;
    setMessageInput("");
    setIsSending(true);

    // Optimistically show user message immediately
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
      // Keep the optimistic user message and append the assistant response
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Failed to send message");
      // Remove the optimistic message on failure and restore input
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      setMessageInput(content);
    } finally {
      setIsSending(false);
    }
  };

  if (!user) return null;

  return (
    <div className="h-screen flex bg-slate-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-4 border-b border-slate-200">
          <button
            onClick={createNewSession}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            <FiPlus /> New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => selectSession(session)}
              className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${
                selectedSession?.id === session.id ? "bg-blue-50" : ""
              }`}
            >
              <p className="font-medium text-slate-900 truncate">
                {session.title}
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {session.message_count} messages
              </p>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-slate-200 text-xs text-slate-600">
          Logged in as: {user.email}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {selectedSession ? (
          <>
            {/* Header */}
            <div className="bg-white border-b border-slate-200 p-4">
              <h2 className="font-semibold text-slate-900">
                {selectedSession.title}
              </h2>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {isLoading ? (
                <div className="text-center text-slate-600 mt-8">
                  Loading messages...
                </div>
              ) : messages.length === 0 ? (
                <div className="text-center text-slate-600 mt-8">
                  Start the conversation by sending a message
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-md px-4 py-2 rounded-lg ${
                        msg.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-slate-200 text-slate-900"
                      }`}
                    >
                      <p className="text-sm">{msg.content}</p>
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-300 border-opacity-50">
                          <p className="text-xs font-medium mb-1">Citations:</p>
                          {msg.citations.map((cite, idx) => (
                            <p key={idx} className="text-xs">
                              [{idx + 1}] {cite.filename} (p. {cite.page_number}
                              )
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t border-slate-200 p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
                  placeholder="Type your message..."
                  disabled={isSending}
                  className="flex-1"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={isSending || !messageInput.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <FiSend /> Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-600">
            {documents.length === 0 ? (
              <p>Upload a document first</p>
            ) : (
              <p>Click New Chat to start</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
