import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Spinner } from "./ui";

export default function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Checking your session…" className="min-h-screen" />;
  if (!user || user.role !== role) {
    return <Navigate to={`/${role}/login`} replace state={{ from: location.pathname }} />;
  }
  return children;
}
