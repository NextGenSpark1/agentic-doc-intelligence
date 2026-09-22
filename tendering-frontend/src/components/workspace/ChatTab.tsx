import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Send, Sparkles, FileText, Maximize2, Minimize2 } from 'lucide-react';
import { chatWithWorkspace } from '../../api/tenders';
import type { ChatCitation } from '../../api/tenders';
import type { TenderWorkspace } from '../../types';

export interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
  citations?: ChatCitation[];
}

export const CHAT_STARTER: ChatMsg[] = [
  {
    role: 'assistant',
    text: "Hi! I'm your AI assistant for this tender. Once you've extracted at least one document, ask me anything — specific clauses, how to address a gap, what a requirement means, or how to structure your proposal.",
  },
];

const PROMPTS = [
  'What are the mandatory requirements I still need to address?',
  'How can we close the biggest compliance gaps?',
  'Summarise the key technical requirements.',
];

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function isTableRow(line: string) {
  return line.trim().startsWith('|') && line.trim().endsWith('|');
}

function isSeparatorRow(line: string) {
  return /^\|[\s\-:|]+\|/.test(line.trim());
}

function parseTableCells(line: string): string[] {
  return line.trim().slice(1, -1).split('|').map((cell) => cell.trim());
}

function MarkdownMessage({ text }: { text: string }) {
  const lines = text.split('\n');
  const nodes: ReactNode[] = [];
  let listItems: string[] = [];
  let listType: 'ul' | 'ol' | null = null;
  let index = 0;

  function flushList() {
    if (!listItems.length) return;
    const Tag = listType!;
    nodes.push(
      <Tag key={nodes.length} className={`pl-4 space-y-0.5 ${Tag === 'ul' ? 'list-disc' : 'list-decimal'} list-outside`}>
        {listItems.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item)}</li>
        ))}
      </Tag>
    );
    listItems = [];
    listType = null;
  }

  while (index < lines.length) {
    const line = lines[index];

    // Detect markdown table block
    if (isTableRow(line) && index + 1 < lines.length && isSeparatorRow(lines[index + 1])) {
      flushList();
      const headers = parseTableCells(line);
      index += 2; // skip header + separator
      const bodyRows: string[][] = [];
      while (index < lines.length && isTableRow(lines[index])) {
        bodyRows.push(parseTableCells(lines[index]));
        index++;
      }
      nodes.push(
        <div key={nodes.length} className="overflow-x-auto my-2">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-panel-3 border-b border-border">
                {headers.map((header, headerIndex) => (
                  <th key={headerIndex} className="text-left px-3 py-2 font-semibold text-text whitespace-nowrap">
                    {renderInline(header)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-b border-border last:border-0 hover:bg-panel-3/50">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 text-text-mid align-top">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    const bulletMatch = line.match(/^[-*]\s+(.*)/);
    const numberedMatch = line.match(/^\d+\.\s+(.*)/);
    const headingMatch = line.match(/^#{1,3}\s+(.*)/);

    if (bulletMatch) {
      if (listType === 'ol') flushList();
      listType = 'ul';
      listItems.push(bulletMatch[1]);
    } else if (numberedMatch) {
      if (listType === 'ul') flushList();
      listType = 'ol';
      listItems.push(numberedMatch[1]);
    } else {
      flushList();
      if (headingMatch) {
        nodes.push(
          <p key={nodes.length} className="font-semibold text-text mt-1">
            {renderInline(headingMatch[1])}
          </p>
        );
      } else if (line.trim()) {
        nodes.push(
          <p key={nodes.length} className="leading-relaxed">
            {renderInline(line)}
          </p>
        );
      } else if (index > 0 && lines[index - 1].trim()) {
        nodes.push(<div key={nodes.length} className="h-1.5" />);
      }
    }
    index++;
  }
  flushList();
  return <div className="text-sm space-y-0.5">{nodes}</div>;
}

export function ChatTab({
  workspace,
  messages,
  onMessages,
}: {
  workspace: TenderWorkspace;
  messages: ChatMsg[];
  onMessages: (updater: (previous: ChatMsg[]) => ChatMsg[]) => void;
}) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userText = input.trim();
    setInput('');
    onMessages((previous) => [...previous, { role: 'user', text: userText }]);
    setLoading(true);

    const history = messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) => ({ role: message.role, content: message.text }));

    try {
      const response = await chatWithWorkspace(workspace.id, userText, history);
      onMessages((previous) => [
        ...previous,
        { role: 'assistant', text: response.answer, citations: response.citations },
      ]);
    } catch {
      onMessages((previous) => [
        ...previous,
        { role: 'assistant', text: 'Something went wrong. Make sure documents have been extracted before asking questions.' },
      ]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  return (
    <div
      className={`bg-panel border border-border rounded-xl overflow-hidden flex flex-col transition-all ${
        expanded
          ? 'fixed inset-x-4 top-[6.5rem] bottom-4 z-40 shadow-2xl'
          : ''
      }`}
      style={expanded ? undefined : { height: 'calc(100vh - 15rem)', minHeight: '420px' }}
    >

      {/* Header */}
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-2 bg-panel-2 flex-shrink-0">
        <div className="w-6 h-6 rounded-full bg-teal/20 flex items-center justify-center">
          <Sparkles size={12} className="text-teal" />
        </div>
        <span className="text-sm font-semibold text-text">AI Tender Assistant</span>
        <span className="ml-auto text-[11px] text-text-mute truncate max-w-[200px] mr-2">
          {workspace.title.split('—')[0].trim()}
        </span>
        <button
          onClick={() => setExpanded((previous) => !previous)}
          className="flex-shrink-0 p-1 rounded hover:bg-panel-3 text-text-mute hover:text-text transition-colors"
          title={expanded ? 'Collapse' : 'Expand'}
        >
          {expanded ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {message.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-teal/10 flex items-center justify-center mr-2 mt-1 flex-shrink-0">
                <Sparkles size={11} className="text-teal" />
              </div>
            )}
            <div className="max-w-[82%] space-y-2">
              <div
                className={`px-4 py-3 rounded-xl ${
                  message.role === 'user'
                    ? 'bg-navy text-white rounded-tr-sm text-sm leading-relaxed'
                    : 'bg-panel-2 border border-border text-text-mid rounded-tl-sm'
                }`}
              >
                {message.role === 'user' ? message.text : <MarkdownMessage text={message.text} />}
              </div>

              {/* Citations */}
              {message.citations && message.citations.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pl-1">
                  {message.citations.slice(0, 6).map((citation, citationIndex) => (
                    <div
                      key={citation.chunk_id || citationIndex}
                      className="group relative flex items-center gap-1.5 px-2.5 py-1.5 bg-panel-3 border border-border rounded-lg text-[11px] text-text-mute hover:border-teal hover:text-teal transition-colors cursor-default"
                    >
                      <FileText size={10} className="flex-shrink-0" />
                      <span className="font-medium">p.{citation.page || '?'}</span>
                      {citation.quoted_text && (
                        <div className="absolute bottom-full left-0 mb-1.5 w-80 max-h-60 overflow-y-auto bg-canvas-deep border border-border rounded-lg p-2.5 text-[11px] text-text-mid leading-snug z-10 hidden group-hover:block shadow-lg">
                          <p className="text-[10px] text-text-mute mb-1 font-semibold uppercase tracking-wide">Source excerpt</p>
                          <p className="italic">"{citation.quoted_text}"</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
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
                {[0, 1, 2].map((dotIndex) => (
                  <div
                    key={dotIndex}
                    className="w-1.5 h-1.5 rounded-full bg-text-mute animate-bounce"
                    style={{ animationDelay: `${dotIndex * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts — only until first user message */}
      {messages.length === 1 && (
        <div className="px-5 py-3 border-t border-border flex gap-2 flex-wrap bg-panel-2 flex-shrink-0">
          {PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => setInput(prompt)}
              className="text-xs px-3 py-1.5 rounded-full bg-panel border border-border text-text-mid hover:border-teal hover:text-teal transition-colors"
            >
              {prompt}
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
