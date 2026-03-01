import Layout from '../components/Layout'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useEffect, useState } from 'react'

const About = () => {
  const [content, setContent] = useState('')

  useEffect(() => {
    // In a real scenario, this would fetch from an API or a local file
    // For now, I'll use a placeholder or try to fetch from the root ABOUT.md
    fetch('/ABOUT.md')
      .then(res => res.text())
      .then(text => setContent(text))
      .catch(() => setContent(`# About Hakeem

Hakeem is a sophisticated AI interface designed for clarity, speed, and wisdom. Built with modern technologies to provide the best user experience.`))
  }, [])

  return (
    <Layout>
      <div className="content-page" style={{ padding: '5rem 15%', minHeight: '60vh' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </Layout>
  )
}

export default About
