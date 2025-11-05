import React, { createContext, useState, useEffect, useContext } from "react";
import api from "../api";
import { useNavigate } from "react-router-dom";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null); // {id, name, email, role, onboardingComplete}
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      const token = localStorage.getItem("token");
      if (token) {
        try {
          const { data } = await api.get("/auth/users/me");
          console.log("User loadedddddd", data);
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

    const { data } = await api.post("/auth/token", formData,{
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    }});
    console.log("Logged in user me.data1:", data);
    localStorage.setItem("token", data.access_token);
    const me = await api.get("/auth/users/me");
    setUser(me.data);
    console.log("Logged in user me.data2:", me.data);
    return me.data;
  
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    await localStorage.setItem("token", data.token);
    const me = await api.get("/auth/users/me");
    setUser(me.data.user);
    return me.data.user;
  };

  const logout = () => {
    localStorage.removeItem("token");
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
