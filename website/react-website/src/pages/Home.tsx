import Layout from '../components/Layout'
import { useNavigate } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

const Home = () => {
  const navigate = useNavigate()
  const featureCardsRef = useRef<HTMLDivElement[]>([])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent, card: HTMLDivElement) => {
      const rect = card.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      card.style.setProperty('--mouse-x', `${x}px`)
      card.style.setProperty('--mouse-y', `${y}px`)
    }

    featureCardsRef.current.forEach(card => {
      if (card) {
        card.addEventListener('mousemove', (e) => handleMouseMove(e, card))
      }
    })

    return () => {
      featureCardsRef.current.forEach(card => {
        if (card) {
          card.removeEventListener('mousemove', (e) => handleMouseMove(e, card))
        }
      })
    }
  }, [])

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2
      }
    }
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  }

  return (
    <Layout>
      <header className="hero">
        <motion.div 
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="hero-content"
        >
          <h1>Intelligence tailored for your needs.</h1>
          <p>Experience Hakeem, a sophisticated AI interface designed for clarity, speed, and wisdom.</p>
          <div className="hero-btns">
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="btn-primary" 
              onClick={() => navigate('/chat')}
              style={{ padding: '1rem 2rem', fontSize: '1.1rem' }}
            >
              Start Chatting
            </motion.button>
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="btn-outline" 
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              style={{ padding: '1rem 2rem', fontSize: '1.1rem' }}
            >
              Learn More
            </motion.button>
          </div>
        </motion.div>
        
        <motion.div 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, delay: 0.2 }}
          className="hero-visual"
        >
          <div className="abstract-shape"></div>
        </motion.div>
      </header>

      <section id="features" style={{ padding: '100px 10%', background: 'var(--bg)' }}>
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '2.5rem' 
          }}
        >
          {[
            { title: "Fast Response", desc: "Powered by optimized API calls for near-instant interaction." },
            { title: "Private & Secure", desc: "Your data is handled with the highest standards of privacy." },
            { title: "Wise Context", desc: "Hakeem remembers your conversation flow for better assistance." }
          ].map((feature, i) => (
            <motion.div 
              key={i}
              variants={itemVariants}
              className="feature-card" 
              ref={el => { if (el) featureCardsRef.current[i] = el }}
              style={{
                background: 'var(--card-bg)',
                padding: '3rem 2rem',
                borderRadius: '32px',
                border: '1px solid var(--border)',
                boxShadow: '0 4px 20px rgba(0,0,0,0.03)',
                textAlign: 'center'
              }}
            >
              <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem', fontWeight: 800 }}>{feature.title}</h3>
              <p style={{ color: 'var(--text-light)', lineHeight: 1.7 }}>{feature.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </section>
    </Layout>
  )
}

export default Home
