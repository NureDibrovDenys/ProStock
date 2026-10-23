import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { AUTH_ENABLED } from '../config';
import { useAuth } from './AuthContext';

export function RequireAuth() {
  const { session } = useAuth();
  const location = useLocation();
  if (AUTH_ENABLED && !session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}
