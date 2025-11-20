import React, { useState } from "react";
import api from "../api";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";

// Listas constantes de datos
const PROVINCIAS_ARGENTINA = [
  "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", 
  "Corrientes", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", 
  "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", 
  "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", 
  "Tierra del Fuego", "Tucumán"
];

const PROFESIONES_COMUNES = [
  "Desarrollador/a", "Diseñador/a", "Estudiante", "Docente", 
  "Médico/a", "Abogado/a", "Contador/a", "Ingeniero/a", "Comerciante", 
  "Administrativo/a", "Otro"
];

const Onboarding = () => {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  
  const [form, setForm] = useState({    
    pais: "Argentina", // Valor por defecto sugerido
    provincia: "",
    localidad: "",
    edad: "",
    nombre: "",
    apellido: "",
    profesion: ""
  });
  
  const [error, setError] = useState(null);
  
  // Estado para controlar visualmente qué opción del select está elegida
  // Si es "Otro", mostramos el input manual.
  const [seleccionProfesion, setSeleccionProfesion] = useState("");

  const onChange = e => setForm({ ...form, [e.target.name]: e.target.value });

  // Manejador especial para el cambio del select de profesión
  const handleProfesionSelect = (e) => {
    const valor = e.target.value;
    setSeleccionProfesion(valor);

    if (valor === "Otro") {
      // Si elige otro, limpiamos la profesión en el form para que escriba una nueva
      setForm({ ...form, profesion: "" });
    } else {
      // Si elige una de la lista, actualizamos el form directamente
      setForm({ ...form, profesion: valor });
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    try {
      console.log("Onboarding response form:", form);
      const { data } = await api.post("/auth/onboarding", form);
      console.log("Onboarding response dataUser:", data);
      setUser(data);
      navigate("/");
    } catch (err) {
      setError(err.response?.data?.message || "Error en onboarding");
    }
  };

  return (
    <div className="max-w-lg mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-2xl mb-4">Completar onboarding</h2>
      <form onSubmit={onSubmit} className="grid gap-3">
        
        <input 
          name="nombre" 
          value={form.nombre} 
          onChange={onChange} 
          placeholder="Nombre" 
          className="p-2 border rounded" 
        />
        
        <input 
          name="apellido" 
          value={form.apellido} 
          onChange={onChange} 
          placeholder="Apellido" 
          className="p-2 border rounded" 
        />
        
        <input 
          name="pais" 
          value={form.pais} 
          onChange={onChange} 
          placeholder="País" 
          className="p-2 border rounded bg-gray-100"
          readOnly // Opcional: si solo admites Argentina por las provincias
        />

        {/* DESPLEGABLE DE PROVINCIAS */}
        <select 
          name="provincia" 
          value={form.provincia} 
          onChange={onChange} 
          className="p-2 border rounded bg-white"
        >
          <option value="">Seleccione una provincia</option>
          {PROVINCIAS_ARGENTINA.map((prov) => (
            <option key={prov} value={prov}>{prov}</option>
          ))}
        </select>

        <input 
          name="localidad" 
          value={form.localidad} 
          onChange={onChange} 
          placeholder="Localidad" 
          className="p-2 border rounded" 
        />
        
        <input 
          name="edad" 
          value={form.edad} 
          onChange={onChange} 
          placeholder="Edad" 
          type="number" 
          className="p-2 border rounded" 
        />

        {/* DESPLEGABLE DE PROFESIÓN */}
        <select 
          value={seleccionProfesion} 
          onChange={handleProfesionSelect} 
          className="p-2 border rounded bg-white"
        >
          <option value="">Seleccione su profesión</option>
          {PROFESIONES_COMUNES.map((prof) => (
            <option key={prof} value={prof}>{prof}</option>
          ))}
        </select>

        {/* INPUT CONDICIONAL: Solo se muestra si seleccionaron "Otro" */}
        {seleccionProfesion === "Otro" && (
          <input 
            name="profesion" 
            value={form.profesion} 
            onChange={onChange} 
            placeholder="Especifique su profesión" 
            className="p-2 border rounded border-blue-400 bg-blue-50 animate-pulse-once" 
            autoFocus
          />
        )}

        {error && <div className="text-red-500 text-sm">{error}</div>}
        
        <button className="bg-green-600 text-white p-2 rounded hover:bg-green-700 transition">
          Guardar
        </button>
      </form>
    </div>
  );
};

export default Onboarding;