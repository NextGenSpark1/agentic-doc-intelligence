import { useEffect, useRef, useState } from 'react';
import { Send, Sparkles } from 'lucide-react';
import type { TenderWorkspace } from '../../types';

interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
}

const STARTER: ChatMsg[] = [
  {
    role: 'assistant',
    text: "Hi! I'm your AI assistant for this tender. I've analysed the uploaded documents and extracted all requirements. Ask me anything — about specific clauses, how to address a gap, or what a term means.",
  },
];

const MOCK_RESPONSES: Record<string, string> = {
  'local workforce':
    "The local workforce requirement (Clause 5.1.a, page 28) mandates ≥40% of total project headcount be nationals. Your current plan is at 28%. To close this gap, you could: (1) partner with a local subcontractor for civil works, (2) hire national technical graduates for support roles, or (3) revise your staffing model to move non-specialist work in-country. Option 1 is fastest before the September 15 deadline.",
  'iso 27001':
    "The ISO/IEC 27001 gap is significant — your certificate expired November 2025. Two paths: (1) Fast-track recertification — most auditors can complete a surveillance audit in 4-6 weeks if your ISMS is already built; or (2) propose a 'certification in progress' letter from the certifying body as interim evidence. Check Clause 7.3 wording — it may allow equivalent standards like SOC 2 Type II as an alternative.",
  noc: "The 24/7 NOC requirement (Clause 7.1) allows for a managed service arrangement — you don't need to own the physical infrastructure. TechOps Ltd or similar ITIL-certified operators could be positioned as a named sub-contractor in Section 4 of your technical proposal. Make sure to include their organisation chart, SLA agreement, and NOC facility details as annexures.",
  default:
    "Based on my analysis of the tender documents, I can see this requirement is detailed in the RFP. Let me know if you'd like a deeper explanation or suggestions on how to address it in your proposal.",
};

const PROMPTS = [
  'How do we address the local workforce gap?',
  'What does the NOC requirement mean exactly?',
  'Can we use an expired ISO 27001 certificate?',
];

export function ChatTab({ workspace }: { workspace: TenderWorkspace }) {
  const [messages, setMessages] = useState<ChatMsg[]>(STARTER);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: userMsg }]);
    setLoading(true);

    await new Promise((r) => setTimeout(r, 1200 + Math.random() * 800));

    const lc = userMsg.toLowerCase();
    const reply =
      lc.includes('local') || lc.includes('workforce') ? MOCK_RESPONSES['local workforce'] :
      lc.includes('27001') || lc.includes('iso 27') || lc.includes('security') ? MOCK_RESPONSES['iso 27001'] :
      lc.includes('noc') || lc.includes('network operations') ? MOCK_RESPONSES['noc'] :
      MOCK_RESPONSES['default'];

    setMessages((m) => [...m, { role: 'assistant', text: reply }]);
    setLoading(false);
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div className="bg-panel border border-border rounded-xl overflow-hidden flex flex-col" style={{ height: '520px' }}>

      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-2 bg-panel-2 flex-shrink-0">
        <div className="w-6 h-6 rounded-full bg-teal/20 flex items-center justify-center">
          <Sparkles size={12} className="text-teal" />
        </div>
        <span className="text-sm font-semibold text-text">AI Tender Assistant</span>
        <span className="ml-auto text-[11px] text-text-mute">
          Context: {workspace.title.split('—')[0].trim()}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-teal/10 flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <Sparkles size={11} className="text-teal" />
              </div>
            )}
            <div
              className={`max-w-[80%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-navy text-white rounded-tr-sm'
                  : 'bg-panel-2 border border-border text-text-mid rounded-tl-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="w-6 h-6 rounded-full bg-teal/10 flex items-center justify-center mr-2 mt-1">
              <Sparkles size={11} className="text-teal" />
            </div>
            <div className="bg-panel-2 border border-border px-4 py-3 rounded-xl rounded-tl-sm">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-text-mute animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts — only shown until first user message */}
      {messages.length === 1 && (
        <div className="px-5 py-3 border-t border-border flex gap-2 flex-wrap bg-panel-2 flex-shrink-0">
          {PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => setInput(p)}
              className="text-xs px-3 py-1.5 rounded-full bg-panel border border-border text-text-mid hover:border-teal hover:text-teal transition-colors"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-5 py-4 border-t border-border flex gap-3 flex-shrink-0">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask about this tender…"
          className="flex-1 px-4 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="w-10 h-10 flex items-center justify-center bg-navy hover:bg-navy-soft disabled:opacity-50 text-white rounded-lg transition-colors"
        >
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}
