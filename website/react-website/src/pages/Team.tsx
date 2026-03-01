import Layout from '../components/Layout'

const Team = () => {
  return (
    <Layout>
      <div className="content-page" style={{ padding: '5rem 15%', minHeight: '60vh', textAlign: 'center' }}>
        <h1>Meet Our Team</h1>
        <p>A group of dedicated individuals working to bring you the best AI experience.</p>
        <div className="team-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem', marginTop: '3rem' }}>
          <div className="team-card">
            <div className="team-avatar" style={{ width: '100px', height: '100px', background: 'var(--primary)', borderRadius: '50%', margin: '0 auto 1rem' }}></div>
            <h3>Jane Doe</h3>
            <p>CEO & Founder</p>
          </div>
          <div className="team-card">
            <div className="team-avatar" style={{ width: '100px', height: '100px', background: 'var(--primary)', borderRadius: '50%', margin: '0 auto 1rem' }}></div>
            <h3>John Smith</h3>
            <p>Lead Engineer</p>
          </div>
          <div className="team-card">
            <div className="team-avatar" style={{ width: '100px', height: '100px', background: 'var(--primary)', borderRadius: '50%', margin: '0 auto 1rem' }}></div>
            <h3>Alex Johnson</h3>
            <p>UI/UX Designer</p>
          </div>
        </div>
      </div>
    </Layout>
  )
}

export default Team
