import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus, prism } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Menu, Moon, Sun, Settings, Send, Trash, X, 
  PlusCircle, Bot, Globe, Cpu, LogOut, Home, ChevronLeft,
  MoreVertical, Edit2, Check
} from 'lucide-react'
import { useMCP } from '../hooks/useMCP'
import { useAuth } from '../context/AuthContext'
import '../styles/chat.css'

interface Message {
  role: 'user' | 'assistant' | 'system' | 'mcp'
  content: string
  timestamp: string
}

interface ChatHistory {
  id: number
  title: string
  messages: Message[]
}

const Chat = () => {
  const navigate = useNavigate()
  const { logout, user } = useAuth()
  const [theme, setTheme] = useState(localStorage.getItem('hakeem-theme') || 'light')
  const [chats, setChats] = useState<ChatHistory[]>([])
  const [currentChatId, setCurrentChatId] = useState<number | null>(null)
  const [userInput, setUserInput] = useState('')
  const [isSidebarOpen, setIsSidebarOpen] = useState(window.innerWidth > 768)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTab, setActiveTab] = useState<'general' | 'mcp'>('general')
  
  // Menu/Edit state
  const [menuOpenChatId, setMenuOpenChatId] = useState<number | null>(null)
  const [editingChatId, setEditingChatId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  
  // MCP Servers
  const [mcpServers, setMcpServers] = useState<string[]>(JSON.parse(localStorage.getItem('hakeem-mcp-servers') || '["http://127.0.0.1/sse"]'))
  const [newMcpUrl, setNewMcpUrl] = useState('')
  const [activeMcpUrl, setActiveMcpUrl] = useState<string | null>(null)
  const { messages: mcpMessages, status: mcpStatus, connect: connectMCP, disconnect: disconnectMCP } = useMCP(activeMcpUrl)

  const [apiProvider, setApiProvider] = useState(localStorage.getItem('hakeem-api-provider') || 'llama-cpp')
  const [apiUrl, setApiUrl] = useState(localStorage.getItem('hakeem-api-url') || 'http://localhost:8080/v1')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Profile image placeholder
  const profileImg = `https://api.dicebear.com/7.x/avataaars/svg?seed=${user?.username || 'Guest'}`

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('hakeem-theme', theme)
  }, [theme])

  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('hakeem-chats') || '[]')
    setChats(savedChats)
    if (savedChats.length > 0) {
      const lastActiveId = localStorage.getItem('hakeem-last-active-chat')
      const chatToLoad = savedChats.find((c: ChatHistory) => c.id === Number(lastActiveId)) || savedChats[savedChats.length - 1]
      setCurrentChatId(chatToLoad.id)
    } else {
      createNewChat()
    }
  }, [])

  useEffect(() => {
    if (currentChatId !== null) {
      localStorage.setItem('hakeem-last-active-chat', String(currentChatId))
    }
    scrollToBottom()
  }, [currentChatId, chats])

  useEffect(() => {
    localStorage.setItem('hakeem-mcp-servers', JSON.stringify(mcpServers))
  }, [mcpServers])

  // Sync MCP messages
  useEffect(() => {
    if (mcpMessages.length > 0 && currentChatId) {
      const lastMsg = mcpMessages[mcpMessages.length - 1]
      const mcpMsg: Message = { 
        role: 'mcp', 
        content: `**[MCP]** ${lastMsg.content}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      addMessageToChat(mcpMsg)
    }
  }, [mcpMessages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const addMessageToChat = (msg: Message) => {
    setChats(prev => {
      const updated = prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, msg] } : c
      )
      localStorage.setItem('hakeem-chats', JSON.stringify(updated))
      return updated
    })
  }

  const createNewChat = () => {
    const newChat: ChatHistory = {
      id: Date.now(),
      title: 'New Conversation',
      messages: []
    }
    const updatedChats = [...chats, newChat]
    setChats(updatedChats)
    localStorage.setItem('hakeem-chats', JSON.stringify(updatedChats))
    setCurrentChatId(newChat.id)
    if (window.innerWidth <= 768) setIsSidebarOpen(false)
  }

  const deleteChat = (id: number) => {
    const updatedChats = chats.filter(c => c.id !== id)
    setChats(updatedChats)
    localStorage.setItem('hakeem-chats', JSON.stringify(updatedChats))
    if (currentChatId === id) {
      if (updatedChats.length > 0) {
        setCurrentChatId(updatedChats[updatedChats.length - 1].id)
      } else {
        createNewChat()
      }
    }
    setMenuOpenChatId(null)
  }

  const startRenaming = (chat: ChatHistory) => {
    setEditingChatId(chat.id)
    setEditTitle(chat.title)
    setMenuOpenChatId(null)
  }

  const saveRename = () => {
    if (editingChatId && editTitle.trim()) {
      const updated = chats.map(c => c.id === editingChatId ? { ...c, title: editTitle } : c)
      setChats(updated)
      localStorage.setItem('hakeem-chats', JSON.stringify(updated))
    }
    setEditingChatId(null)
  }

  const handleSendMessage = async () => {
    if (!userInput.trim() || isStreaming || currentChatId === null) return

    const chat = chats.find(c => c.id === currentChatId)
    if (!chat) return

    const userMsg: Message = { 
      role: 'user', 
      content: userInput,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    
    let updatedTitle = chat.title
    if (chat.messages.length === 0) {
      updatedTitle = userInput.substring(0, 30) + (userInput.length > 30 ? '...' : '')
    }

    const updatedMessages = [...chat.messages, userMsg]
    const updatedChats = chats.map(c => c.id === currentChatId ? { ...c, title: updatedTitle, messages: updatedMessages } : c)
    setChats(updatedChats)
    localStorage.setItem('hakeem-chats', JSON.stringify(updatedChats))
    setUserInput('')
    setIsStreaming(true)

    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    try {
      await simulateAIResponse(currentChatId, updatedMessages)
    } catch (error) {
      console.error("Chat error:", error)
    } finally {
      setIsStreaming(false)
    }
  }

  const simulateAIResponse = async (chatId: number, baseMessages: Message[]) => {
    const fullText = `I am Hakeem, your AI assistant. Everything is now optimized for clarity and speed!

\`\`\`javascript
const hakeem = {
  status: "Optimized",
  ui: "Modern",
  icons: "SVG"
};
\`\`\``
    
    let currentText = ""
    const assistantMsg: Message = { 
      role: 'assistant', 
      content: '', 
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) 
    }

    for (let i = 0; i < fullText.length; i++) {
      currentText += fullText[i]
      setChats(prev => prev.map(c => 
        c.id === chatId 
        ? { ...c, messages: [...baseMessages, { ...assistantMsg, content: currentText }] } 
        : c
      ))
      await new Promise(r => setTimeout(r, 10))
    }
    
    const finalChats = JSON.parse(localStorage.getItem('hakeem-chats') || '[]')
    const finalUpdated = finalChats.map((c: ChatHistory) => 
      c.id === chatId 
      ? { ...c, messages: [...baseMessages, { ...assistantMsg, content: fullText }] } 
      : c
    )
    localStorage.setItem('hakeem-chats', JSON.stringify(finalUpdated))
    setChats(finalUpdated)
  }

  const addMcpServer = () => {
    if (newMcpUrl && !mcpServers.includes(newMcpUrl)) {
      setMcpServers([...mcpServers, newMcpUrl])
      setNewMcpUrl('')
    }
  }

  const removeMcpServer = (url: string) => {
    setMcpServers(mcpServers.filter(u => u !== url))
    if (activeMcpUrl === url) {
      disconnectMCP()
      setActiveMcpUrl(null)
    }
  }

  const currentChat = chats.find(c => c.id === currentChatId)

  return (
    <div className="chat-page">
      <nav className="navbar">
        <div className="nav-left">
          <button className="icon-btn sidebar-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
            {isSidebarOpen ? <ChevronLeft size={22} /> : <Menu size={22} />}
          </button>
          <Link to="/" className="logo-brand">
            <span className="logo-text">HAKEEM</span>
            <div className={`status-pill ${mcpStatus}`}>
              <div className="dot" />
              <span>{mcpStatus === 'connected' ? 'MCP LINKED' : 'STANDBY'}</span>
            </div>
          </Link>
        </div>

        <div className="nav-right">
          <button className="icon-btn theme-toggle" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
            {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
          </button>
          <button className="icon-btn settings-toggle" onClick={() => setIsSettingsOpen(true)}>
            <Settings size={20} />
          </button>
        </div>
      </nav>

      <div className="chat-wrapper">
        <aside className={`sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
          <button className="new-chat-btn" onClick={createNewChat}>
            <PlusCircle size={20} />
            <span>New Chat</span>
          </button>
          
          <div className="history-list">
            <div className="section-title">Conversations</div>
            {chats.slice().reverse().map(chat => (
              <div 
                key={chat.id} 
                className={`history-item ${chat.id === currentChatId ? 'active' : ''}`}
                onClick={() => {
                  if (editingChatId !== chat.id) {
                    setCurrentChatId(chat.id)
                    if (window.innerWidth <= 768) setIsSidebarOpen(false)
                  }
                }}
              >
                <div className="item-icon-box"><Globe size={16} /></div>
                
                {editingChatId === chat.id ? (
                  <input 
                    autoFocus
                    className="edit-title-input"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveRename(); if (e.key === 'Escape') setEditingChatId(null); }}
                    onBlur={saveRename}
                  />
                ) : (
                  <span className="title">{chat.title}</span>
                )}

                <div className="item-actions">
                  {editingChatId === chat.id ? (
                    <button onClick={saveRename} className="action-btn-small"><Check size={14} /></button>
                  ) : (
                    <button 
                      className="action-btn-small menu-trigger" 
                      onClick={(e) => { e.stopPropagation(); setMenuOpenChatId(menuOpenChatId === chat.id ? null : chat.id); }}
                    >
                      <MoreVertical size={14} />
                    </button>
                  )}
                </div>

                <AnimatePresence>
                  {menuOpenChatId === chat.id && (
                    <motion.div 
                      initial={{ opacity: 0, scale: 0.95, y: -10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: -10 }}
                      className="item-dropdown-menu"
                    >
                      <button onClick={() => startRenaming(chat)} className="dropdown-btn">
                        <Edit2 size={14} /> <span>Rename</span>
                      </button>
                      <button onClick={() => deleteChat(chat.id)} className="dropdown-btn delete">
                        <Trash size={14} /> <span>Delete</span>
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>

          <div className="sidebar-footer">
            <div className="user-card">
              <div className="user-avatar-img">
                <img src={profileImg} alt="Profile" />
              </div>
              <div className="user-meta">
                <span className="name">{user?.username || 'Guest User'}</span>
                <span className="plan">Standard Account</span>
              </div>
            </div>
            <div className="footer-actions">
              <button className="footer-action-btn" onClick={() => navigate('/')}>
                <Home size={20} />
                <span>Return Home</span>
              </button>
              <button className="footer-action-btn logout" onClick={logout}>
                <LogOut size={20} />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </aside>

        <main className="chat-main">
          <div className="messages-container">
            {currentChat?.messages.length === 0 ? (
              <div className="welcome-hero">
                <div className="hero-icon"><Bot size={48} /></div>
                <h1>How can I help you today?</h1>
                <p>Knowledge, wisdom, and code at your fingertips.</p>
                <div className="chips">
                  {['Explain Quantum Computing', 'Write a Python Script', 'Summarize this article'].map(t => (
                    <button key={t} onClick={() => setUserInput(t)} className="hero-chip">{t}</button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages-list">
                {currentChat?.messages.map((msg, idx) => (
                  <motion.div 
                    key={idx} 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`message-row ${msg.role}`}
                  >
                    <div className="avatar">
                      {msg.role === 'user' ? (
                        <div className="msg-avatar-img"><img src={profileImg} alt="User" /></div>
                      ) : (msg.role === 'mcp' ? <Cpu size={20} /> : <Bot size={20} />)}
                    </div>
                    <div className="message-content-wrapper">
                      <div className="message-bubble">
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({ node, inline, className, children, ...props }: any) {
                              const match = /language-(\w+)/.exec(className || '')
                              return !inline && match ? (
                                <SyntaxHighlighter
                                  style={theme === 'dark' ? vscDarkPlus : prism}
                                  language={match[1]}
                                  PreTag="div"
                                  {...props}
                                >
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              ) : (
                                <code className={className} {...props}>
                                  {children}
                                </code>
                              )
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                      <span className="msg-time">{msg.timestamp}</span>
                    </div>
                  </motion.div>
                ))}
                {isStreaming && (
                  <div className="streaming-indicator">
                    <div className="dot" />
                    <div className="dot" />
                    <div className="dot" />
                  </div>
                )}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-wrapper">
            <div className="chat-input-container">
              <textarea 
                ref={textareaRef}
                value={userInput}
                onChange={(e) => {
                  setUserInput(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSendMessage()
                  }
                }}
                placeholder="Ask Hakeem anything..." 
                rows={1}
              />
              <button 
                className={`send-button ${userInput.trim() ? 'active' : ''}`}
                onClick={handleSendMessage}
                disabled={isStreaming || !userInput.trim()}
              >
                <Send size={20} />
              </button>
            </div>
            <div className="chat-input-footer">Hakeem AI v1.5.0 • Precise SVG Rendering</div>
          </div>
        </main>
      </div>

      <AnimatePresence>
        {isSettingsOpen && (
          <div className="modal-overlay" onClick={() => setIsSettingsOpen(false)}>
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="modal-card" 
              onClick={e => e.stopPropagation()}
            >
              <div className="modal-header">
                <h3>Settings</h3>
                <button className="icon-btn" onClick={() => setIsSettingsOpen(false)}><X size={20} /></button>
              </div>
              
              <div className="modal-tabs">
                <button className={`modal-tab ${activeTab === 'general' ? 'active' : ''}`} onClick={() => setActiveTab('general')}>General</button>
                <button className={`modal-tab ${activeTab === 'mcp' ? 'active' : ''}`} onClick={() => setActiveTab('mcp')}>MCP Hub</button>
              </div>

              <div className="modal-body">
                {activeTab === 'general' ? (
                  <div className="tab-pane">
                    <div className="form-group">
                      <label>AI Provider</label>
                      <select value={apiProvider} onChange={(e) => setApiProvider(e.target.value)}>
                        <option value="llama-cpp">Llama.cpp</option>
                        <option value="openai">OpenAI</option>
                        <option value="ollama">Ollama</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>API Endpoint</label>
                      <input type="text" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
                    </div>
                  </div>
                ) : (
                  <div className="tab-pane">
                    <div className="mcp-list">
                      {mcpServers.map(url => (
                        <div key={url} className="mcp-item">
                          <span className="url">{url}</span>
                          <div className="actions">
                            <button 
                              onClick={() => { activeMcpUrl === url ? (disconnectMCP(), setActiveMcpUrl(null)) : (setActiveMcpUrl(url), connectMCP()) }}
                              className={`mcp-btn ${activeMcpUrl === url ? 'active' : ''}`}
                            >
                              {activeMcpUrl === url ? 'Linked' : 'Link'}
                            </button>
                            <button onClick={() => removeMcpServer(url)} className="delete-mcp"><Trash size={14} /></button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="add-mcp-box">
                      <input type="text" placeholder="SSE URL..." value={newMcpUrl} onChange={(e) => setNewMcpUrl(e.target.value)} />
                      <button onClick={addMcpServer} className="add-btn"><PlusCircle size={20} /></button>
                    </div>
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button className="save-btn" onClick={() => setIsSettingsOpen(false)}>Save Changes</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default Chat
