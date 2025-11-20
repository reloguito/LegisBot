import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";

const Register = () => {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const onChange = e => setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setIsLoading(true);
    
    try {
      // Registrar (ahora incluye login automático internamente)
      const user = await register(form);
      console.log("Usuario registrado y logueado:", user);
      setSuccess(true);
      
      // Verificar onboarding y redirigir
      const completed = user?.has_completed_onboarding;
      console.log("Onboarding completado:", completed);

      // Redirigir después de un breve delay
      setTimeout(() => {
        if (completed) {
          navigate("/");
        } else {
          navigate("/onboarding");
        }
      }, 1500);
      
    } catch (err) {
      console.error("Error en registro:", err);
      setError(err.response?.data?.detail || err.response?.data?.message || "Error al registrar");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-2xl mb-4">Registrarse</h2>
      <form onSubmit={onSubmit} className="space-y-3">
        <input 
          name="email" 
          value={form.email} 
          onChange={onChange} 
          placeholder="Email" 
          type="email"
          className="w-full p-2 border rounded" 
          required
        />
        <input 
          name="password" 
          value={form.password} 
          onChange={onChange} 
          placeholder="Contraseña" 
          type="password" 
          className="w-full p-2 border rounded" 
          required
          minLength="6"
        />
        
        {error && (
          <div className="text-red-500 bg-red-50 p-2 rounded">
            {error}
          </div>
        )}
        
        {success && (
          <div className="text-green-600 bg-green-50 p-2 rounded border border-green-200">
            ✅ Registro exitoso! Redirigiendo...
          </div>
        )}
        
        <button 
          type="submit"
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 transition duration-200 disabled:bg-blue-300"
          disabled={!form.email || !form.password || isLoading}
        >
          {isLoading ? "Registrando..." : "Crear cuenta"}
        </button>
      </form>
    </div>
  );
};

export default Register;