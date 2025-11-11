import React, { useEffect, useState } from 'react';
// 1. Importamos tanto Pie como Bar
import { Pie, Bar } from 'react-chartjs-2'; 
import {
  Chart as ChartJS,
  // Componentes para Pie
  ArcElement, 
  // Componentes para Bar
  CategoryScale,
  LinearScale,
  BarElement,
  // Componentes comunes
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import api from "../api";

// 2. Registramos TODOS los elementos que necesitamos
ChartJS.register(
  ArcElement,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

const AdminCharts = () => {
  // 3. Creamos estados separados para cada gráfico
  const [pieChartData, setPieChartData] = useState(null);
  const [barChartData, setBarChartData] = useState(null);
  // ESTADO NUEVO para el 3er gráfico
  const [queriesChartData, setQueriesChartData] = useState(null); 
  
  const [pieLoading, setPieLoading] = useState(true);
  const [barLoading, setBarLoading] = useState(true);
  // ESTADO NUEVO para el 3er gráfico
  const [queriesLoading, setQueriesLoading] = useState(true); 

  // 4. useEffect para el gráfico de Torta (Demographics)
  useEffect(() => {
    api
      .get("/admin/stats/demographics")
      .then((res) => {
        const apiData = res.data || [];
        const labels = apiData.map(item => item.group);
        const counts = apiData.map(item => item.count);

        setPieChartData({
          labels: labels,
          datasets: [
            {
              label: '# de Usuarios',
              data: counts,
              backgroundColor: [
                'rgba(255, 99, 132, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 206, 86, 0.6)',
                'rgba(75, 192, 192, 0.6)',
                'rgba(153, 102, 255, 0.6)',
                'rgba(255, 159, 64, 0.6)',
              ],
              borderColor: [ /* ... */ ],
              borderWidth: 1,
            },
          ],
        });
        setPieLoading(false);
      })
      .catch((err) => {
        console.error("Error cargando datos demográficos:", err);
        setPieLoading(false);
      });
  }, []);

  // 5. useEffect para el gráfico de Barras (Usage)
  useEffect(() => {
    api
      .get("/admin/stats/usage")
      .then((res) => {
        const apiData = res.data || [];
        
        const labels = apiData.map(item => {
          try {
            return new Date(item.date).toLocaleDateString();
          } catch (e) {
            return item.date;
          }
        });
        const counts = apiData.map(item => item.count);

        setBarChartData({
          labels: labels,
          datasets: [
            {
              label: 'Uso por Día',
              data: counts,
              backgroundColor: 'rgba(54, 162, 235, 0.6)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1,
            },
          ],
        });
        setBarLoading(false);
      })
      .catch((err) => {
        console.error("Error cargando datos de uso:", err);
        setBarLoading(false);
      });
  }, []);

  // 6. NUEVO useEffect para el gráfico de Barras Horizontales (Top Queries)
  useEffect(() => {
    api
      .get("/admin/stats/top-queries")
      .then((res) => {
        const apiData = res.data || [];
        
        // El JSON es [{"group": "...", "count": 0}]
        const labels = apiData.map(item => item.group);
        const counts = apiData.map(item => item.count);

        setQueriesChartData({
          labels: labels, // Las preguntas largas van en 'labels'
          datasets: [
            {
              label: 'Nº de Consultas',
              data: counts,
              backgroundColor: 'rgba(75, 192, 192, 0.6)', // Color verde azulado
              borderColor: 'rgba(75, 192, 192, 1)',
              borderWidth: 1,
            },
          ],
        });
        setQueriesLoading(false);
      })
      .catch((err) => {
        console.error("Error cargando top queries:", err);
        setQueriesLoading(false);
      });
  }, []);


  // 7. Opciones separadas para cada gráfico
  const pieOptions = {
    responsive: true,
    plugins: {
      legend: { position: 'top' },
      title: {
        display: true,
        text: 'Estadísticas Demográficas',
      },
    },
  };

  const barOptions = {
    responsive: true,
    plugins: {
      legend: { position: 'top' },
      title: {
        display: true,
        text: 'Uso del Sistema por Día',
      },
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  };

  // 8. NUEVAS Opciones para el gráfico de Queries (Horizontal)
  const queriesOptions = {
    indexAxis: 'y', // <-- ESTO LO HACE HORIZONTAL
    responsive: true,
    plugins: {
      legend: {
        display: false, // Ocultamos la leyenda, es redundante
      },
      title: {
        display: true,
        text: 'Consultas Más Frecuentes',
      },
    },
    scales: {
      x: { // El eje numérico ahora es X
        beginAtZero: true
      }
    }
  };


  // 9. Renderizamos los tres gráficos
  return (
    // Hacemos el contenedor principal un poco más ancho
    <div style={{ width: '100%', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* Contenedor FLEX para los primeros dos gráficos (lado a lado) */}
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'wrap',
        justifyContent: 'space-around',
        alignItems: 'center'
      }}>

        {/* --- Sección Demografía (Gráfico de Torta) --- */}
        <div style={{ width: '100%', maxWidth: '400px', margin: '20px' }}>
          {pieLoading && <div>Cargando estadísticas demográficas...</div>}
          {!pieLoading && !pieChartData && <div>No hay datos demográficos para mostrar.</div>}
          {!pieLoading && pieChartData && (
            <Pie data={pieChartData} options={pieOptions} />
          )}
        </div>

        {/* --- Sección Uso (Gráfico de Barras) --- */}
        <div style={{ width: '100%', maxWidth: '500px', margin: '20px' }}>
          {barLoading && <div>Cargando estadísticas de uso...</div>}
          {!barLoading && !barChartData && <div>No hay datos de uso para mostrar.</div>}
          {!barLoading && barChartData && (
            <Bar data={barChartData} options={barOptions} />
          )}
        </div>
      
      </div> {/* Fin del contenedor Flex */}

      <hr style={{ margin: '40px 0' }} />

      {/* --- NUEVA Sección Top Queries (Gráfico Horizontal) --- */}
      {/* Este div está FUERA del flex, por lo tanto aparece DEBAJO */}
      <div style={{ width: '100%', maxWidth: '1000px', margin: '40px auto' }}>
        {queriesLoading && <div>Cargando top queries...</div>}
        {!queriesLoading && (!queriesChartData || queriesChartData.labels.length === 0) && <div>No hay queries para mostrar.</div>}
        {!queriesLoading && queriesChartData && queriesChartData.labels.length > 0 && (
          <Bar data={queriesChartData} options={queriesOptions} />
        )}
      </div>

    </div>
  );
};

export default AdminCharts;