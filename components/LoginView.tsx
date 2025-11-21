import React, { useState } from 'react';
import { UserCircleIcon, LockIcon } from './icons';

interface LoginViewProps {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, email: string, password: string, fullName: string) => Promise<void>;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLogin, onRegister }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      if (isLogin) {
        await onLogin(username, password);
      } else {
        if (!email || !fullName) {
          setError('Please fill in all fields');
          setIsLoading(false);
          return;
        }
        await onRegister(username, email, password, fullName);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="w-full max-w-md p-8 bg-surface rounded-lg shadow-xl border border-gray-700">
        <div className="flex justify-center mb-6">
          <UserCircleIcon className="w-16 h-16 text-primary" />
        </div>

        <h2 className="text-3xl font-bold text-center text-white mb-2">
          {isLogin ? 'Welcome Back' : 'Create Account'}
        </h2>
        <p className="text-center text-gray-400 mb-8">
          {isLogin ? 'Sign in to your account' : 'Register for CDSA'}
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-md text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
              required
              disabled={isLoading}
            />
          </div>

          {!isLogin && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
                  required
                  disabled={isLoading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-4 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
                  required
                  disabled={isLoading}
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-background border border-gray-600 rounded-md text-white focus:outline-none focus:border-primary"
              required
              minLength={12}
              disabled={isLoading}
              placeholder="Min 12 chars, uppercase, lowercase, digit, special"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 bg-primary hover:bg-primary-dark text-white font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          >
            <LockIcon className="w-5 h-5" />
            <span>{isLoading ? 'Please wait...' : (isLogin ? 'Sign In' : 'Register')}</span>
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
            className="text-primary hover:text-primary-dark text-sm transition-colors"
            disabled={isLoading}
          >
            {isLogin ? "Don't have an account? Register" : 'Already have an account? Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
};