import { useState, useRef, useEffect, useMemo } from 'react'
import type { Document as CaseDocument, Citation } from '../types'
import { sendChatMessage } from '../api'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

const SUGGESTIONS = [
  'Summarize the key findings across all documents',
  'Who are the main entities or people mentioned?',
  'What timeline of events can you identify?',
]

function IIAvatar() {
  return (
    <div className="w-7 h-7 bg-navy flex items-center justify-center rounded font-mono font-bold text-teal text-[11px] shrink-0 mb-0.5 shadow-sm">
      II
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <IIAvatar />
      <div className="bg-panel-2 border border-border rounded-2xl rounded-bl-sm px-4 py-3.5 flex items-center gap-1.5">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="w-1.5 h-1.5 bg-text-mute rounded-full animate-bounce"
            style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
          />
        ))}
      </div>
    </div>
  )
}

function CitationBadge({ n }: { n: number }) {
  return (
    <sup className="inline-flex items-center justify-center w-[18px] h-[18px] text-[9px] font-bold bg-teal text-white rounded-full mx-0.5 cursor-default select-none align-middle">
      {n}
    </sup>
  )
}

function parseAnswer(text: string): React.ReactNode[] {
  const parts = text.split(/(\[\d+\])/g)
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/)
    if (m) return <CitationBadge key={i} n={Number(m[1])} />
    return <span key={i}>{part}</span>
  })
}

export default function CaseAssistantPanel({
  caseId,
  docs,
  onCitationClick,
}: {
  caseId: string
  docs: CaseDocument[]
  onCitationClick?: (documentId: string, page: number) => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [openCitations, setOpenCitations] = useState<Set<string>>(new Set())
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const docMap = useMemo(
    () => Object.fromEntries(docs.map(d => [d.document_id, d.filename])),
    [docs],
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  function adjustTextarea() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || loading) return

    const history = messages.map(m => ({ role: m.role, content: m.content }))
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: msg }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setLoading(true)

    try {
      const response = await sendChatMessage(caseId, msg, history)
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
        },
      ])
    } catch {
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Sorry, I ran into an error processing your request. Please try again.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 py-4 flex flex-col gap-4 min-h-0">
        {messages.length === 0 && !loading ? (
          <div className="flex flex-col items-center gap-5 py-6 px-1">
            <div className="w-12 h-12 bg-navy flex items-center justify-center rounded-xl font-mono font-bold text-teal text-base shadow-sm">
              II
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold text-text">Case Assistant</p>
              <p className="text-xs text-text-mute mt-1 leading-relaxed">
                Ask anything about the documents extracted in this case
              </p>
            </div>
            <div className="flex flex-col gap-2 w-full">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="w-full text-left text-xs text-text-mid bg-panel-2 hover:bg-panel-3 border border-border hover:border-border-strong rounded-xl px-3 py-2.5 transition-colors duration-150 leading-relaxed"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map(msg =>
              msg.role === 'user' ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[82%] bg-teal text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-xs leading-relaxed break-words">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div key={msg.id} className="flex items-end gap-2">
                  <IIAvatar />
                  <div className="max-w-[87%] flex flex-col gap-2 min-w-0">
                    <div className="bg-panel-2 border border-border rounded-2xl rounded-bl-sm px-4 py-3 text-xs text-text leading-relaxed break-words">
                      {parseAnswer(msg.content)}
                    </div>
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="flex flex-col gap-1 ml-0.5">
                        {/* Collapsible sources toggle */}
                        <button
                          onClick={() => setOpenCitations(prev => {
                            const next = new Set(prev)
                            next.has(msg.id) ? next.delete(msg.id) : next.add(msg.id)
                            return next
                          })}
                          className="flex items-center gap-1.5 text-[10px] font-semibold text-text-mute hover:text-text transition-colors duration-150 w-fit"
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                            className={`transition-transform duration-150 ${openCitations.has(msg.id) ? 'rotate-90' : ''}`}>
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                          Sources ({msg.citations.length})
                        </button>
                        {openCitations.has(msg.id) && (
                          <div className="flex flex-col gap-1.5">
                            {msg.citations.map((c, i) => {
                              const clickable = Boolean(onCitationClick)
                              return (
                                <div
                                  key={c.chunk_id}
                                  onClick={clickable ? () => onCitationClick?.(c.document_id, c.page) : undefined}
                                  className={`bg-panel border border-border rounded-xl px-3 py-2.5 flex flex-col gap-1.5 transition-colors duration-150
                                    ${clickable ? 'cursor-pointer hover:bg-panel-3 hover:border-border-strong' : ''}`}
                                >
                                  <div className="flex items-center gap-2">
                                    <sup className="inline-flex items-center justify-center w-[18px] h-[18px] text-[9px] font-bold bg-teal text-white rounded-full shrink-0">
                                      {i + 1}
                                    </sup>
                                    <span className="text-[10px] font-semibold text-text truncate flex-1">
                                      {docMap[c.document_id] ?? c.document_id}
                                    </span>
                                    <span className="text-[10px] font-semibold text-teal bg-teal/10 border border-teal/20 px-1.5 py-0.5 rounded-full shrink-0">
                                      p.&nbsp;{c.page + 1}
                                    </span>
                                  </div>
                                  {c.quoted_text && (
                                    <p className="text-[10px] text-text-mute leading-relaxed line-clamp-3 border-l-2 border-teal/30 pl-2 italic">
                                      &ldquo;{c.quoted_text}&rdquo;
                                    </p>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ),
            )}
            {loading && <TypingIndicator />}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-3 shrink-0">
        <div className="flex items-end gap-2 bg-panel-2 border border-border-strong rounded-xl px-3 py-2 focus-within:border-teal focus-within:ring-2 focus-within:ring-teal/20 transition-colors duration-150">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => {
              setInput(e.target.value)
              adjustTextarea()
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Ask the assistant… (Enter to send)"
            rows={1}
            className="flex-1 bg-transparent text-xs text-text placeholder:text-text-mute resize-none focus:outline-none leading-relaxed"
            style={{ minHeight: '1.25rem', maxHeight: '7.5rem' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="shrink-0 w-7 h-7 flex items-center justify-center bg-teal hover:bg-teal-soft text-white rounded-lg transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Send message"
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-text-mute mt-1.5 text-center leading-tight">
          Searches all extracted documents in this case
        </p>
      </div>
    </div>
  )
}
