import Layout from '../components/Layout'

const Sales = () => {
  return (
    <Layout>
      <div className="content-page" style={{ padding: '5rem 15%', minHeight: '60vh', textAlign: 'center' }}>
        <h1>Enterprise Solutions</h1>
        <p>Take your business to the next level with Hakeem Enterprise.</p>
        <div style={{ marginTop: '3rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          <div className="feature-card">
            <h3>Custom Deployment</h3>
            <p>Deploy Hakeem on your own infrastructure for maximum security.</p>
          </div>
          <div className="feature-card">
            <h3>Priority Support</h3>
            <p>Get 24/7 dedicated support from our expert team.</p>
          </div>
          <div className="feature-card">
            <h3>Advanced Analytics</h3>
            <p>Gain insights into how your team is using AI.</p>
          </div>
        </div>
        <button className="btn-primary btn-lg" style={{ marginTop: '3rem' }}>Contact Sales Team</button>
      </div>
    </Layout>
  )
}

export default Sales
