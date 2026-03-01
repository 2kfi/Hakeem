import { useState, useEffect, useCallback } from 'react'

export interface MCPMessage {
  type: 'message' | 'status' | 'error'
  content: string
}

export const useMCP = (url: string | null) => {
  const [messages, setMessages] = useState<MCPMessage[]>([])
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected')
  const [eventSource, setEventSource] = useState<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!url) return
    
    setStatus('connecting')
    const es = new EventSource(url)

    es.onopen = () => {
      setStatus('connected')
    }

    es.onerror = (e) => {
      console.error('MCP SSE Error:', e)
      setStatus('disconnected')
      es.close()
    }

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages(prev => [...prev, { type: 'message', content: data.message || data.content || event.data }])
      } catch (err) {
        setMessages(prev => [...prev, { type: 'message', content: event.data }])
      }
    }

    setEventSource(es)
  }, [url])

  const disconnect = useCallback(() => {
    if (eventSource) {
      eventSource.close()
      setEventSource(null)
      setStatus('disconnected')
    }
  }, [eventSource])

  useEffect(() => {
    return () => {
      if (eventSource) eventSource.close()
    }
  }, [eventSource])

  return { messages, status, connect, disconnect }
}
