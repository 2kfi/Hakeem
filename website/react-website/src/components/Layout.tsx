import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const Layout = ({ children }: { children: React.ReactNode }) => {
  const [theme, setTheme] = useState(localStorage.getItem('hakeem-theme') || 'light')
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('hakeem-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <div className="layout-wrapper">
      <nav className="navbar">
        <Link to="/" className="logo">HAKEEM</Link>
        <div className="nav-links">
          <motion.button 
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={toggleTheme} 
            className="btn-secondary" 
            title="Toggle Theme"
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </motion.button>
          <a href="/#features">Features</a>
          <button className="btn-secondary" onClick={() => navigate('/login')}>Login</button>
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="btn-primary" 
            onClick={() => navigate('/chat')}
          >
            Get Started
          </motion.button>
        </div>
      </nav>

      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
        >
          {children}
        </motion.main>
      </AnimatePresence>

      <footer className="site-footer">
        <div className="footer-container">
          <div className="footer-col">
            <div className="logo">HAKEEM</div>
            <p>Intelligence tailored for your needs.</p>
          </div>

          <div className="footer-col">
            <h4>Resources</h4>
            <ul>
              <li><Link to="/contact">Contact Us</Link></li>
              <li><Link to="/about">About Us</Link></li>
              <li><Link to="/team">Team Members</Link></li>
              <li><a href="#">Blog</a></li>
            </ul>
          </div>

          <div className="footer-col">
            <h4>Sales</h4>
            <ul>
              <li><Link to="/sales">Contact Sales</Link></li>
              <li><Link to="/demo">Request a Demo</Link></li>
              <li><a href="#">Pricing Plans</a></li>
            </ul>
          </div>

          <div className="footer-col">
            <h4>Our Office</h4>
            <p>123 Innovation Way<br />
              Tech District, Suite 400<br />
              San Francisco, CA 94105</p>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; 2026 Nullnet. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

export default Layout
