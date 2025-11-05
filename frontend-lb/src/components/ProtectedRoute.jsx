import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

const ProtectedRoute = ({ children, adminOnly = false }) => {
  const { user, loading } = useAuth();
  const userData = useAuth();
  console.log("ProtectedRoute userData:", userData);

  if (loading) return <div className="p-4">Cargando...</div>;
  console.log("ProtectedRoute user:", user);
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;

  return children;
};

export default ProtectedRoute;
