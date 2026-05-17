import { Navigate, Outlet } from 'react-router-dom';
import { isTokenValid } from '../lib/adminApi';

export function AdminGuard() {
  if (!isTokenValid()) {
    return <Navigate to="/admin/login" replace />;
  }
  return <Outlet />;
}
