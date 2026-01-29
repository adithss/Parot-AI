
import React, { useState, useEffect, useRef } from 'react';
import { ParotLogo } from './icons';

interface LoginPageProps {
  onLoginSuccess: () => void;
  onNavigateToSignup: () => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess, onNavigateToSignup }) => {
  const vantaRef = useRef<HTMLDivElement>(null);
  const vantaEffectRef = useRef<any>(null); // Use ref
  const [msg, setMsg] = useState({ text: '', type: '' });
  const [formData, setFormData] = useState({ email: '', password: '' });

  useEffect(() => {
    const loadVanta = () => {
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
    const timer = setInterval(loadVanta, 200);

    return () => { 
        clearInterval(timer);
        if (vantaEffectRef.current) {
            vantaEffectRef.current.destroy();
            vantaEffectRef.current = null;
        }
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setMsg({ text: '', type: '' });

    if(!formData.email || !formData.password){
      setMsg({ text: "Please fill all fields.", type: 'error' });
      return;
    }

    // Verify credentials if users exist in storage
    const storedUsers = localStorage.getItem('parotUsers');
    if (storedUsers) {
        const users = JSON.parse(storedUsers);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const validUser = users.find((u: any) => u.email === formData.email && u.password === formData.password);
        
        if (!validUser) {
            setMsg({ text: "Invalid email or password.", type: 'error' });
            return;
        }
    }

    setMsg({ text: "Signing in…", type: '' });
    setTimeout(() => {
        onLoginSuccess();
    }, 800);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData({...formData, [e.target.id]: e.target.value});
  };

  return (
    <>
      <div id="vanta-bg" ref={vantaRef}></div>

      <header className="site-header">
        <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ParotLogo className="w-8 h-8" />
            <span style={{ fontWeight: 'bold', fontSize: '1.25rem', letterSpacing: '-0.025em', color: '#fff' }}>parot</span>
        </div>
      </header>

      <main className="signup-viewport">
        <div className="signup-card">
          <h2 style={{ marginBottom: '6px', fontSize: '1.5rem', fontWeight: 700 }}>Welcome back</h2>
          <div className="small muted" style={{ marginBottom: '18px' }}>Sign in to continue</div>

          <form id="loginForm" onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" placeholder="you@company.com" value={formData.email} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input id="password" type="password" placeholder="••••••••" value={formData.password} onChange={handleChange} required />
            </div>

            <button type="submit" className="btn primary" style={{ width: '100%', marginTop: '8px' }}>Sign In</button>
          </form>

          <div className={`msg ${msg.type}`} id="msg">{msg.text}</div>

          <div className="small muted" style={{ marginTop: '16px', textAlign: 'center' }}>
            Don't have an account?{' '}
            <button onClick={onNavigateToSignup} className="muted-link" style={{background:'none', border:'none', padding:0, cursor:'pointer'}}>Create Account</button>
          </div>
        </div>
      </main>

      <footer className="site-footer">
        © PAROT — Meeting Intelligence
      </footer>
    </>
  );
};

export default LoginPage;
