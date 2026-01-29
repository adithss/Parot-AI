
import React, { useState, useEffect, useRef } from 'react';
import { ParotLogo } from './icons';

interface LandingPageProps {
  onNavigate: (view: string) => void;
}

const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  const vantaRef = useRef<HTMLDivElement>(null);
  const vantaEffectRef = useRef<any>(null); // Use ref to track instance
  const [isNavOpen, setIsNavOpen] = useState(false);

  useEffect(() => {
    const loadVanta = () => {
      // Only initialize if not already exists
      if (!vantaEffectRef.current && (window as any).VANTA && vantaRef.current) {
        try {
          vantaEffectRef.current = (window as any).VANTA.TOPOLOGY({
            el: vantaRef.current,
            mouseControls: true,
            touchControls: true,
            gyroControls: false,
            minHeight: 200.00,
            minWidth: 200.00,
            scale: 1.00,
            scaleMobile: 1.00,
            color: 0x0891b2, 
            backgroundColor: 0x0f1724 
          });
        } catch (e) {
          console.error("Failed to initialize Vanta:", e);
        }
      }
    };

    loadVanta();
    const timer = setInterval(loadVanta, 200); // Check periodically if script loads

    return () => {
      clearInterval(timer);
      if (vantaEffectRef.current) {
        vantaEffectRef.current.destroy();
        vantaEffectRef.current = null;
      }
    };
  }, []);

  return (
    <>
      <div id="vanta-bg" ref={vantaRef}></div>

      <header className="site-header">
        <div className="logo" onClick={() => onNavigate('landing')} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
             <ParotLogo className="w-8 h-8" />
             <span style={{ fontWeight: 'bold', fontSize: '1.25rem', letterSpacing: '-0.025em', color: '#fff' }}>parot</span>
        </div>

        <nav className={`nav ${isNavOpen ? 'open' : ''}`} id="nav">
          <button onClick={() => { setIsNavOpen(false); document.getElementById('home')?.scrollIntoView({behavior: 'smooth'}) }}>Home</button>
          <button onClick={() => { setIsNavOpen(false); document.getElementById('features')?.scrollIntoView({behavior: 'smooth'}) }}>Features</button>
          <button onClick={() => onNavigate('login')}>Log In</button>
          <button onClick={() => onNavigate('signup')} style={{ color: 'var(--accent)' }}>Sign Up</button>
        </nav>

        <div className="right">
          <button 
            id="menuBtn" 
            className="menu-btn" 
            aria-label="Toggle menu"
            onClick={() => setIsNavOpen(!isNavOpen)}
          >
            ☰
          </button>
        </div>
      </header>

      <main className="container">

        {/* HERO */}
        <section className="hero" id="home">
          <div className="hero-left">
            <span className="eyebrow">Real-time • Summaries</span>
            <h1>PAROT — Meetings made actionable</h1>
            <p className="lead">Live transcription, short summaries and automatic task extraction — simple and private for teams.</p>
            <div className="cta">
              <button className="btn primary" onClick={() => onNavigate('dashboard')}>Try Demo</button>
              <button className="btn ghost" onClick={() => onNavigate('signup')}>Create Account</button>
            </div>
          </div>

          <div className="hero-right">
            <div className="dashboard-window">
              <div className="window-header">
                <div className="window-dots">
                  <div className="window-dot" style={{background: '#ff5f56'}}></div>
                  <div className="window-dot" style={{background: '#ffbd2e'}}></div>
                  <div className="window-dot" style={{background: '#27c93f'}}></div>
                </div>
                <div className="window-bar"></div>
              </div>
              <div className="window-body">
                <div className="window-sidebar">
                  <div className="sidebar-item active"></div>
                  <div className="sidebar-item"></div>
                  <div className="sidebar-item"></div>
                </div>
                <div className="window-main">
                  <div className="window-hero-card">
                    <div className="sk-line title"></div>
                    <div className="sk-line"></div>
                    <div className="sk-line w-80"></div>
                  </div>
                  <div className="window-grid">
                     <div className="window-card">
                       <div className="sk-line title w-50"></div>
                       <div className="sk-box"></div>
                     </div>
                     <div className="window-card">
                       <div className="sk-line title w-50"></div>
                       <div className="sk-line"></div>
                       <div className="sk-line"></div>
                     </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section className="features" id="features">
          <div className="feature">
            <h3>Live Transcript</h3>
            <p>Accurate captions with speaker names and timestamps.</p>
          </div>

          <div className="feature">
            <h3>Smart Summaries</h3>
            <p>Short summaries showing decisions and next steps.</p>
          </div>

          <div className="feature">
            <h3>Action Items</h3>
            <p>Automatic task extraction with due dates and owners.</p>
          </div>
        </section>

      </main>

      <footer className="site-footer">
        © PAROT — Meeting Intelligence
      </footer>
    </>
  );
};

export default LandingPage;
