import { FormEvent, useState } from "react";

interface LoginPageProps {
  onLoginSuccess: (user: UserData) => void;
  onSwitchToSignup: () => void;
  apiBase: string;
}

export interface UserData {
  email: string;
  name: string;
  surname: string;
}

const LoginPage = ({ onLoginSuccess, onSwitchToSignup, apiBase }: LoginPageProps) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Login with Basic Auth
      const credentials = btoa(`${email}:${password}`);
      const loginRes = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: {
          Authorization: `Basic ${credentials}`,
          "Content-Type": "application/json",
        },
        credentials: "include", // Important for cookies
      });

      if (!loginRes.ok) {
        const data = await loginRes.json().catch(() => ({}));
        throw new Error(data.error || "Invalid credentials");
      }

      // Fetch user info after successful login
      const userRes = await fetch(`${apiBase}/auth/user`, {
        method: "POST",
        credentials: "include",
      });

      if (!userRes.ok) {
        throw new Error("Failed to fetch user info");
      }

      const userData: UserData = await userRes.json();
      onLoginSuccess(userData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">data/cow</div>
          <h1>Welcome back</h1>
          <p>Sign in to continue to your workspace</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="auth-switch">
          Don't have an account?{" "}
          <button type="button" className="link-button" onClick={onSwitchToSignup}>
            Sign up
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
