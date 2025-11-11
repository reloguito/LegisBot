import React, { useEffect, useState } from "react";
import api from "../api";

const History = () => {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api.get("/chat/history").then(res =>       
      setHistory(res.data || [])
    ).catch(()=>{});
  }, []);

   return (
    <div className="max-w-3xl mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-xl font-semibold mb-4">Historial de chat</h2>

      {history.length === 0 && (
        <p className="text-gray-600">No tenés consultas todavía.</p>
      )}

      <ul>
        {history.map((chat) => (
          <li key={chat.id} className="mb-6 p-4 border rounded-lg bg-gray-50">
            <div className="text-sm text-gray-500 mb-2">
              <span className="font-medium">Sesión:</span>{" "}
              {new Date(chat.created_at).toLocaleString()}
            </div>

            {chat.messages.map((msg, idx) => (
              <div key={msg.id || idx} className="mb-3">
                {msg.sender === "user" ? (
                  <div className="bg-blue-50 border-l-4 border-blue-400 p-2 rounded">
                    <strong>👤 Usuario:</strong> {msg.content}
                  </div>
                ) : (
                  <div className="bg-green-50 border-l-4 border-green-400 p-2 rounded">
                    <strong>🤖 Bot:</strong> {msg.content}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-1 text-xs text-gray-600">
                        <strong>Fuentes:</strong>{" "}
                        {msg.sources.map((s, i) => (
                          <div key={i} className="ml-2">
                            📄 {s.source} (pág. {s.page})
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default History;
