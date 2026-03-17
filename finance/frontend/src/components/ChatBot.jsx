import { useState, useRef, useEffect } from 'react';

const ACTION_BADGES = {
  Modify: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  Delete: 'bg-red-500/20 text-red-400 border-red-500/30',
  Add: 'bg-green-500/20 text-green-400 border-green-500/30',
};

function formatAED(text) {
  return text.replace(
    /(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*AED/g,
    (_, num) => `AED ${num}`
  );
}

function renderMessageText(text) {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    const isBullet = /^[\-\*]\s/.test(line.trim());
    const formatted = formatAED(line).replace(
      /\*\*(.+?)\*\*/g,
      '<strong class="font-semibold text-gray-50">$1</strong>'
    );

    if (isBullet) {
      return (
        <li
          key={i}
          className="ml-4 list-disc text-sm"
          dangerouslySetInnerHTML={{ __html: formatted.replace(/^[\-\*]\s/, '') }}
        />
      );
    }
    return (
      <p
        key={i}
        className="text-sm"
        dangerouslySetInnerHTML={{ __html: formatted }}
      />
    );
  });
}

function ActionCard({ action, onApprove, onReject }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const badgeStyle = ACTION_BADGES[action.action_type] || ACTION_BADGES.Modify;

  async function handleApprove() {
    setLoading(true);
    try {
      const res = await fetch(import.meta.env.VITE_API_URL + '/api/chat/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          action_type: action.action_type,
          payload: action.payload,
        }),
      });
      if (!res.ok) throw new Error('Execution failed');
      setStatus('approved');
      onApprove();
    } catch {
      setStatus('error');
    } finally {
      setLoading(false);
    }
  }

  if (status === 'approved') {
    return (
      <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-400">
        Action completed successfully.
      </div>
    );
  }

  if (status === 'rejected' || status === 'error') return null;

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-xs font-medium border ${badgeStyle}`}>
          {action.action_type}
        </span>
      </div>
      <p className="text-sm text-gray-300">{action.description}</p>
      <div className="flex gap-2">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-500 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Processing...' : 'Approve'}
        </button>
        <button
          onClick={() => setStatus('rejected')}
          className="rounded bg-gray-700 px-3 py-1 text-xs font-medium text-gray-300 hover:bg-gray-600 transition-colors"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

export default function ChatBot({ onRefresh }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function sendMessage(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(import.meta.env.VITE_API_URL + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          message: text,
          history: updated.filter((m) => !m.actions),
        }),
      });

      if (res.status === 401) {
        window.location.href = 'https://aldhaheri.co';
        return;
      }
      if (!res.ok) throw new Error(`API error: ${res.status}`);

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message,
          actions: data.actions || null,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong. Please try again.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Floating chat button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-purple-600 text-white shadow-lg hover:bg-purple-500 transition-all duration-200 hover:scale-105"
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      <div
        className={`fixed bottom-24 right-6 z-50 flex flex-col overflow-hidden rounded-xl border border-gray-800 bg-gray-950 shadow-2xl transition-all duration-300 origin-bottom-right ${
          open
            ? 'w-[400px] h-[500px] opacity-100 scale-100'
            : 'w-0 h-0 opacity-0 scale-95 pointer-events-none'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-400" />
            <h3 className="text-sm font-semibold text-gray-100">Finance Assistant</h3>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
            aria-label="Close chat"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.length === 0 && (
            <div className="flex h-full items-center justify-center">
              <p className="text-center text-sm text-gray-500">
                Ask about your transactions, spending, or balances.
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className="max-w-[85%] space-y-2">
                <div
                  className={`rounded-lg border px-3 py-2 ${
                    msg.role === 'user'
                      ? 'bg-blue-600/20 border-blue-500/30 text-gray-100'
                      : 'bg-gray-800/50 border-gray-700/30 text-gray-300'
                  }`}
                >
                  {renderMessageText(msg.content)}
                </div>

                {msg.actions && msg.actions.length > 0 && (
                  <div className="space-y-2">
                    {msg.actions.map((action, j) => (
                      <ActionCard
                        key={j}
                        action={action}
                        onApprove={() => onRefresh?.()}
                        onReject={() => {}}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-lg border border-gray-700/30 bg-gray-800/50 px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.3s]" />
                  <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.15s]" />
                  <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <form onSubmit={sendMessage} className="border-t border-gray-800 bg-gray-900 px-3 py-2">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask something..."
              disabled={loading}
              className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-purple-600 text-white hover:bg-purple-500 disabled:opacity-40 disabled:hover:bg-purple-600 transition-colors"
              aria-label="Send message"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
