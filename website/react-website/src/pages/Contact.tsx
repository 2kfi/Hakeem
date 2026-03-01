import Layout from '../components/Layout'
import { motion } from 'framer-motion'
import { Mail, MessageSquare, User, Send } from 'lucide-react'

const Contact = () => {
  return (
    <Layout>
      <div className="content-page" style={{ padding: '5rem 10%', minHeight: '80vh' }}>
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ maxWidth: '800px', margin: '0 auto' }}
        >
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '1rem' }}>Get in Touch</h1>
            <p style={{ color: 'var(--text-light)', fontSize: '1.1rem' }}>
              Have questions about Hakeem? Our team is here to help you navigate the world of AI.
            </p>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '3rem' 
          }}>
            <div className="contact-info">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ width: '48px', height: '48px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)' }}>
                    <Mail size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Email Us</h3>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-light)' }}>support@hakeem.ai</p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <div style={{ width: '48px', height: '48px', background: 'rgba(139, 92, 246, 0.1)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)' }}>
                    <MessageSquare size={24} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Live Chat</h3>
                    <p style={{ margin: '4px 0 0', color: 'var(--text-light)' }}>Available 24/7 for Enterprise</p>
                  </div>
                </div>
              </div>
            </div>

            <form style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: '1.5rem',
              background: 'var(--card-bg)',
              padding: '2rem',
              borderRadius: '24px',
              border: '1px solid var(--border)',
              boxShadow: '0 10px 30px rgba(0,0,0,0.05)'
            }}>
              <div className="input-group">
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', opacity: 0.8 }}>Name</label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <User size={18} style={{ position: 'absolute', left: '1rem', color: 'var(--text-light)' }} />
                  <input 
                    type="text" 
                    placeholder="Your Name" 
                    style={{ 
                      width: '100%', 
                      padding: '0.85rem 1rem 0.85rem 3rem', 
                      borderRadius: '12px', 
                      border: '1px solid var(--border)',
                      background: 'var(--bg)',
                      color: 'var(--text)',
                      outline: 'none'
                    }} 
                  />
                </div>
              </div>
              
              <div className="input-group">
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', opacity: 0.8 }}>Email</label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <Mail size={18} style={{ position: 'absolute', left: '1rem', color: 'var(--text-light)' }} />
                  <input 
                    type="email" 
                    placeholder="Your Email" 
                    style={{ 
                      width: '100%', 
                      padding: '0.85rem 1rem 0.85rem 3rem', 
                      borderRadius: '12px', 
                      border: '1px solid var(--border)',
                      background: 'var(--bg)',
                      color: 'var(--text)',
                      outline: 'none'
                    }} 
                  />
                </div>
              </div>

              <div className="input-group">
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', opacity: 0.8 }}>Message</label>
                <textarea 
                  placeholder="How can we help?" 
                  rows={5} 
                  style={{ 
                    width: '100%', 
                    padding: '1rem', 
                    borderRadius: '12px', 
                    border: '1px solid var(--border)',
                    background: 'var(--bg)',
                    color: 'var(--text)',
                    outline: 'none',
                    resize: 'none'
                  }}
                ></textarea>
              </div>

              <button type="submit" className="btn-primary" style={{ padding: '1rem', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem' }}>
                <span>Send Message</span>
                <Send size={18} />
              </button>
            </form>
          </div>
        </motion.div>
      </div>
    </Layout>
  )
}

export default Contact
