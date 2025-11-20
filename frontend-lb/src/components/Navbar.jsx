import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

const Navbar = () => {
  const { user, logout } = useAuth();
  return (
    <nav className="bg-white shadow p-4 flex justify-between">
      <div className="flex items-center space-x-4">
        <Link to="/" className="font-bold text-lg">LegisBot</Link>
        {user && <Link to="/chat" className="text-sm">Chat</Link>}
        {user && <Link to="/history" className="text-sm">Historial</Link>}
        {user?.role === "admin" && <Link to="/admin/upload" className="text-sm">Admin Upload</Link>}
        {user?.role === "admin" && <Link to="/admin/stats" className="text-sm">Estadísticas</Link>}
      </div>
      <div>
        {!user ? (
          <>
            <Link to="/login" className="mr-4">Iniciar sesión</Link>
            <Link to="/register" className="ml-4">Registrarse</Link>
          </>
        ) : (
          <div className="flex items-center gap-4">
            <span className="text-sm">Hola, {user.nombre}</span>
            <button onClick={logout} className="bg-red-500 text-white px-3 py-1 rounded">Salir</button>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
