import React, { useState, useEffect } from "react";
import api from "../api";

const ChatPage = () => {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [contexts, setContexts] = useState([]);
  const [selectedContext, setSelectedContext] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    api.get("/documents/contexts").then(res => {
      setContexts(res.data.contexts || []);
      if (res.data.contexts?.length) setSelectedContext(res.data.contexts[0].id);
    }).catch(()=>{});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    
    const userMsg = { role: "user", text: question };
    const loadingMsg = { role: "loading", text: "LegisBot está buscando la respuesta..." };
    
    setMessages(m => [...m, userMsg, loadingMsg]);
    setQuestion("");
    setIsLoading(true);

    try {
      const quest = { query: question, history_id: null };
      const { data } = await api.post("/chat/query", quest);
      
      // Reemplazar mensaje de carga con respuesta real
      setMessages(m => m.map(msg => 
        msg.role === "loading" ? { role: "assistant", text: data.answer } : msg
      ));
      
    } catch (err) {
      // Reemplazar mensaje de carga con error
      setMessages(m => m.map(msg => 
        msg.role === "loading" ? { role: "assistant", text: "Error: no se pudo consultar el servidor." } : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-semibold mb-4">Chat (Consulta documentos)</h2>

      <div className="mb-4">
        <label className="block text-sm">Realiza tu consulta sobre la Versión Taquigrafica:</label>
        
      </div>

      <div className="border p-3 rounded h-64 overflow-auto mb-3 bg-gray-50">
        {messages.map((m, i) => (
          <div key={i} className={`mb-3 ${m.role === "user" ? "text-right" : "text-left"}`}>
            <div className={`inline-block p-2 rounded max-w-[80%] ${
              m.role === "user" ? "bg-blue-100" : 
              m.role === "loading" ? "bg-yellow-100 italic" : 
              "bg-gray-100"
            }`}>
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="flex gap-2">
        <input 
          value={question} 
          onChange={(e) => setQuestion(e.target.value)} 
          placeholder="Hacé una pregunta sobre los documentos..." 
          className="flex-1 p-2 border rounded"
          disabled={isLoading}
        />
        <button 
          className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition duration-200 disabled:bg-green-300"
          disabled={isLoading || !question.trim()}
        >
          {isLoading ? "Buscando..." : "Preguntar"}
        </button>
      </form>
    </div>
  );
};

export default ChatPage;