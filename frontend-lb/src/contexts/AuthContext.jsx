import React, { createContext, useState, useEffect, useContext } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      const token = localStorage.getItem("token");
      if (token) {
        try {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          const { data } = await api.get("/auth/users/me");
          console.log("User loaded", data);
          setUser(data);
        } catch (err) {
          console.error("Token invalid", err);
          localStorage.removeItem("token");
          setUser(null);
        }
      }
      setLoading(false);
    };
    load();
  }, []);

  const login = async (username, password) => {
    const formData = new FormData();
    formData.append("username", username);
    formData.append("password", password);

    const { data } = await api.post("/auth/token", formData, {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      }
    });
    
    console.log("Login token response:", data);
    localStorage.setItem("token", data.access_token);
    
    // Configurar el header de autorización para futuras requests
    api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;
    
    const me = await api.get("/auth/users/me");
    setUser(me.data);
    console.log("Logged in user:", me.data);
    return me.data;
  };

  const register = async (payload) => {
    try {
      // 1. Registrar el usuario
      const { data } = await api.post("/auth/register", payload);
      console.log("Register response:", data);
      
      // 2. Hacer login automáticamente después del registro
      const user = await login(payload.email, payload.password);
      return user;
      
    } catch (error) {
      console.error("Register error:", error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    delete api.defaults.headers.common['Authorization'];
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);