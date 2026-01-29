
import React, { useState, useEffect, useRef } from 'react';
import { ParotLogo } from './icons';

interface SignupPageProps {
  onSignupSuccess: () => void;
  onNavigateToLogin: () => void;
}

const SignupPage: React.FC<SignupPageProps> = ({ onSignupSuccess, onNavigateToLogin }) => {
  const vantaRef = useRef<HTMLDivElement>(null);
  const vantaEffectRef = useRef<any>(null); // Use ref
  const [msg, setMsg] = useState({ text: '', type: '' });
  const [formData, setFormData] = useState({
    fullname: '',
    email: '',
    password: '',
    confirm: ''
  });

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

    const { fullname, email, password, confirm } = formData;

    if(!fullname || !email || !password || !confirm){
      setMsg({ text: "Please fill all fields.", type: 'error' });
      return;
    }

    if(password !== confirm){
      setMsg({ text: "Passwords do not match.", type: 'error' });
      return;
    }

    // Check if email already exists
    const storedUsers = localStorage.getItem('parotUsers');
    const users = storedUsers ? JSON.parse(storedUsers) : [];
    
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if (users.some((u: any) => u.email === email)) {
        setMsg({ text: "This email has been already used.", type: 'error' });
        return;
    }

    // Save new user
    users.push({ fullname, email, password });
    localStorage.setItem('parotUsers', JSON.stringify(users));

    setMsg({ text: "Creating account…", type: '' });
    setTimeout(() => {
        setMsg({ text: "Account created! Redirecting to login…", type: 'success' });
        setTimeout(onSignupSuccess, 1000);
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
          <h2 style={{ marginBottom: '6px', fontSize: '1.5rem', fontWeight: 700 }}>Create your PAROT account</h2>
          <div className="small muted" style={{ marginBottom: '18px' }}>Start managing meetings and summaries instantly</div>

          <form id="signupForm" onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="fullname">Full Name</label>
              <input id="fullname" type="text" placeholder="Your name" value={formData.fullname} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" placeholder="you@company.com" value={formData.email} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input id="password" type="password" placeholder="••••••••" value={formData.password} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label htmlFor="confirm">Confirm Password</label>
              <input id="confirm" type="password" placeholder="••••••••" value={formData.confirm} onChange={handleChange} required />
            </div>

            <button type="submit" className="btn primary" style={{ width: '100%', marginTop: '8px' }}>Create Account</button>
          </form>

          <div className={`msg ${msg.type}`} id="msg">{msg.text}</div>

          <div className="small muted" style={{ marginTop: '16px', textAlign: 'center' }}>
            Already have an account?{' '}
            <button onClick={onNavigateToLogin} className="muted-link" style={{background:'none', border:'none', padding:0, cursor:'pointer'}}>Sign in</button>
          </div>
        </div>
      </main>

      <footer className="site-footer">
        © PAROT — Meeting Intelligence
      </footer>
    </>
  );
};

export default SignupPage;
