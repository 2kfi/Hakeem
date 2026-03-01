import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Login from './pages/Login'
import Chat from './pages/Chat'
import About from './pages/About'
import Team from './pages/Team'
import Contact from './pages/Contact'
import Sales from './pages/Sales'
import Demo from './pages/Demo'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'
import './App.css'
import './styles/style.css'
import './styles/responsive.css'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route 
          path="/chat" 
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          } 
        />
        <Route path="/about" element={<About />} />
        <Route path="/team" element={<Team />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/sales" element={<Sales />} />
        <Route path="/demo" element={<Demo />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
