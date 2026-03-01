import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Mail, Lock, User, ArrowRight, Github } from 'lucide-react'
import '../styles/login.css'

const Login = () => {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/chat'

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, navigate, from])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // For now, allow any non-empty login
    login(isLogin ? email : username)
    setIsLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-background">
        <div className="glass-blob blob-1"></div>
        <div className="glass-blob blob-2"></div>
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="login-card"
      >
        <div className="login-header">
          <div className="login-logo" onClick={() => navigate('/')}>
            <div className="logo-icon"><Shield size={24} /></div>
            <span>HAKEEM</span>
          </div>
          <h1>{isLogin ? 'Welcome back' : 'Create Account'}</h1>
          <p>{isLogin ? 'Enter your details to access your chats' : 'Join Hakeem today for wise AI assistance'}</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <AnimatePresence mode="wait">
            {!isLogin && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="input-wrapper"
              >
                <label>Username</label>
                <div className="input-field">
                  <User size={18} />
                  <input 
                    type="text" 
                    placeholder="ai_explorer" 
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required={!isLogin}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="input-wrapper">
            <label>Email Address</label>
            <div className="input-field">
              <Mail size={18} />
              <input 
                type="email" 
                placeholder="name@example.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required 
              />
            </div>
          </div>

          <div className="input-wrapper">
            <label>Password</label>
            <div className="input-field">
              <Lock size={18} />
              <input 
                type="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required 
              />
            </div>
          </div>

          {isLogin && (
            <div className="form-options">
              <label className="checkbox-container">
                <input type="checkbox" />
                <span className="checkmark"></span>
                Remember me
              </label>
              <a href="#" className="forgot-password">Forgot password?</a>
            </div>
          )}

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? (
              <div className="loader"></div>
            ) : (
              <>
                <span>{isLogin ? 'Sign In' : 'Sign Up'}</span>
                <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>

        <div className="login-divider">
          <span>Or continue with</span>
        </div>

        <div className="social-login">
          <button className="social-btn"><Github size={20} /> GitHub</button>
          <button className="social-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.84z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l2.85 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Google
          </button>
        </div>

        <div className="login-footer">
          <p>
            {isLogin ? "Don't have an account?" : "Already have an account?"}
            <button onClick={() => setIsLogin(!isLogin)} className="toggle-auth">
              {isLogin ? 'Create one' : 'Sign In'}
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  )
}

export default Login
