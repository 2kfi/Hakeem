import Layout from '../components/Layout'

const Demo = () => {
  return (
    <Layout>
      <div className="content-page" style={{ padding: '5rem 15%', minHeight: '60vh', textAlign: 'center' }}>
        <h1>Request a Demo</h1>
        <p>See Hakeem in action. We'll show you how it can transform your workflow.</p>
        <div style={{ maxWidth: '500px', margin: '3rem auto' }}>
          <form style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', textAlign: 'left' }}>
            <div className="input-group">
              <label>Company Name</label>
              <input type="text" placeholder="Your Company" style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid var(--border)' }} />
            </div>
            <div className="input-group">
              <label>Role</label>
              <input type="text" placeholder="Your Role" style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid var(--border)' }} />
            </div>
            <button type="submit" className="btn-primary" style={{ padding: '1rem' }}>Schedule Demo</button>
          </form>
        </div>
      </div>
    </Layout>
  )
}

export default Demo
