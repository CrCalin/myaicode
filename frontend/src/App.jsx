import { useState, useEffect, useRef } from 'react'
import { Plus, MessageSquare, Send, Bot, User, ChevronDown, ChevronRight, Terminal } from 'lucide-react'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'
import './index.css'

marked.setOptions({
  highlight: function(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  }
});

const API_BASE = 'http://localhost:5000/api';

function ToolAccordion({ toolName, args, result }) {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <div className="tool-accordion">
      <div className="tool-header" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Terminal size={14} />
        <span>Used {toolName}</span>
      </div>
      {isOpen && (
        <div className="tool-body">
          <div style={{ color: '#60a5fa', marginBottom: '8px' }}>
            {args && JSON.stringify(JSON.parse(args), null, 2)}
          </div>
          <div>{result || 'Running...'}</div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [approvalRequest, setApprovalRequest] = useState(null);
  
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      const data = await res.json();
      setSessions(data.sessions);
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, metrics, approvalRequest]);

  const loadSession = async (name) => {
    try {
      const res = await fetch(`${API_BASE}/session/${name}`);
      const data = await res.json();
      setCurrentSession(data.session_name);
      
      // Parse state history into UI messages
      const loadedMessages = [];
      if (data.state && data.state.messages) {
        data.state.messages.forEach(msg => {
          if (msg.role === 'system') return;
          if (msg.role === 'user') {
            loadedMessages.push({ role: 'user', content: msg.content });
          } else if (msg.role === 'assistant') {
            if (msg.content) {
              loadedMessages.push({ role: 'assistant', content: msg.content });
            }
            if (msg.tool_calls) {
               msg.tool_calls.forEach(tc => {
                 loadedMessages.push({
                   role: 'tool_call',
                   id: tc.id,
                   name: tc.function.name,
                   args: tc.function.arguments,
                   result: null
                 });
               });
            }
          } else if (msg.role === 'tool') {
             const tcMsg = loadedMessages.find(m => m.role === 'tool_call' && m.id === msg.tool_call_id);
             if (tcMsg) tcMsg.result = msg.content;
          }
        });
      }
      setMessages(loadedMessages);
      setApprovalRequest(null);
      setMetrics(null);
    } catch (e) {
      console.error(e);
    }
  };

  const streamChat = async (payload) => {
    setIsGenerating(true);
    setMetrics(null);
    setApprovalRequest(null);
    
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let currentAssistantMessage = "";
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (!dataStr) continue;
            
            try {
              const event = JSON.parse(dataStr);
              
              if (event.type === 'session_info') {
                 if (event.session_name !== currentSession) {
                     setCurrentSession(event.session_name);
                     fetchSessions(); // Refresh list
                 }
              }
              else if (event.type === 'content') {
                currentAssistantMessage += event.text;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  const last = newMsgs[newMsgs.length - 1];
                  if (last && last.role === 'assistant' && !last.isFinished) {
                    last.content = currentAssistantMessage;
                  } else {
                    newMsgs.push({ role: 'assistant', content: currentAssistantMessage });
                  }
                  return newMsgs;
                });
              }
              else if (event.type === 'metrics') {
                setMetrics({ tokens: event.tokens, elapsed: event.elapsed });
              }
              else if (event.type === 'system') {
                 // You could display system thoughts if you want
              }
              else if (event.type === 'approval_needed') {
                 setApprovalRequest({ command: event.command, tool_call: event.tool_call });
              }
              else if (event.type === 'done') {
                setMessages(prev => {
                   const newMsgs = [...prev];
                   const last = newMsgs[newMsgs.length - 1];
                   if (last && last.role === 'assistant') last.isFinished = true;
                   return newMsgs;
                });
              }
            } catch (e) {
              console.error("JSON parse error:", e, dataStr);
            }
          }
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
      fetchSessions(); // Refresh session list after turn
    }
  };

  const handleSend = () => {
    if (!input.trim() || isGenerating) return;
    
    const userMsg = input;
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    streamChat({ message: userMsg, session_name: currentSession });
  };

  const handleApprove = (approved) => {
    if (!approvalRequest) return;
    const req = approvalRequest;
    setApprovalRequest(null);
    streamChat({ 
      session_name: currentSession, 
      resume_tool_call: req.tool_call, 
      approved 
    });
  };

  const onTextareaInput = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <div className="sidebar">
        <button 
          className="sidebar-btn" 
          onClick={() => { setCurrentSession(null); setMessages([]); }}
        >
          <Plus size={16} /> New Chat
        </button>
        
        <div className="session-list">
          {sessions.map(s => (
            <div 
              key={s} 
              className={`session-item ${s === currentSession ? 'active' : ''}`}
              onClick={() => loadSession(s)}
            >
              <MessageSquare size={14} />
              {s}
            </div>
          ))}
        </div>
      </div>

      <div className="main-content">
        <div className="chat-container">
          {messages.length === 0 ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
              <h1>MyAICode Agent</h1>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`message-row ${msg.role === 'assistant' ? 'assistant' : ''}`}>
                <div className="message-content">
                  <div className={`avatar ${msg.role === 'user' ? 'user' : 'assistant'}`}>
                    {msg.role === 'user' ? <User size={18} color="white" /> : <Bot size={18} color="white" />}
                  </div>
                  
                  {msg.role === 'tool_call' ? (
                     <div style={{flexGrow: 1}}>
                       <ToolAccordion toolName={msg.name} args={msg.args} result={msg.result} />
                     </div>
                  ) : (
                    <div 
                      className="markdown-body"
                      dangerouslySetInnerHTML={{ __html: msg.role === 'user' ? msg.content.replace(/\n/g, '<br/>') : marked(msg.content) }}
                    />
                  )}
                </div>
              </div>
            ))
          )}

          {approvalRequest && (
            <div className="message-row assistant">
              <div className="message-content">
                <div className="avatar assistant"><Bot size={18} color="white" /></div>
                <div className="approval-box">
                  <div style={{color: 'var(--danger)', fontWeight: 'bold', marginBottom: '8px'}}>Approval Required</div>
                  <div style={{fontFamily: 'monospace', marginBottom: '16px'}}>{approvalRequest.command}</div>
                  <button className="approval-btn" onClick={() => handleApprove(true)}>Allow</button>
                  <button className="approval-btn deny" onClick={() => handleApprove(false)}>Deny</button>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="input-box">
            {metrics && isGenerating && (
              <div className="metrics-badge">
                {metrics.tokens} tokens • {metrics.elapsed.toFixed(1)}s
              </div>
            )}
            <textarea
              ref={textareaRef}
              rows="1"
              placeholder="Send a message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onInput={onTextareaInput}
              onKeyDown={onKeyDown}
            />
            <button 
              className="send-button" 
              onClick={handleSend}
              disabled={!input.trim() || isGenerating}
            >
              <Send size={18} />
            </button>
          </div>
          <div style={{textAlign: 'center', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px'}}>
            MyAICode local agent. Responses are generated locally and streamed.
          </div>
        </div>
      </div>
    </>
  );
}
