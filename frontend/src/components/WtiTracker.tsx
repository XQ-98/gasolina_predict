'use client';

import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3, Loader2 } from 'lucide-react';
import dynamic from 'next/dynamic';
import { fetchWtiPrice } from '@/lib/api';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function WtiTracker() {
  const [data, setData] = useState<WtiData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchWtiPrice();
      setData(result);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="w-5 h-5 text-petroleo-400" />
          <h3 className="card-header mb-0">Precio WTI</h3>
        </div>
        <p className="text-sm text-slate-500">No se pudo cargar el precio del WTI</p>
      </div>
    );
  }

  const changes = [
    { label: '24h', value: data.change_24h },
    { label: '7d', value: data.change_7d },
    { label: '30d', value: data.change_30d },
  ];

  const last30 = data.historical.slice(-30);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-petroleo-400" />
          <h3 className="text-sm font-semibold text-white">Petroleo WTI</h3>
        </div>
        <div className="text-right">
          <span className="text-2xl font-bold text-white">
            ${data.current.toFixed(2)}
          </span>
          <span className="text-xs text-slate-400 ml-1">USD/barril</span>
        </div>
      </div>

      {/* Cambios porcentuales */}
      <div className="flex gap-3 mb-4">
        {changes.map((c) => {
          const isUp = c.value > 0;
          const isZero = c.value === 0;
          return (
            <div key={c.label} className="flex-1 bg-slate-800/50 rounded-lg p-2 text-center">
              <span className="text-xs text-slate-500 block">{c.label}</span>
              <div className="flex items-center justify-center gap-1 mt-1">
                {isZero ? (
                  <Minus className="w-3 h-3 text-slate-400" />
                ) : isUp ? (
                  <TrendingUp className="w-3 h-3 text-emerald-400" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-red-400" />
                )}
                <span
                  className={`text-sm font-medium ${
                    isZero
                      ? 'text-slate-400'
                      : isUp
                      ? 'text-emerald-400'
                      : 'text-red-400'
                  }`}
                >
                  {isUp ? '+' : ''}
                  {c.value.toFixed(2)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Sparkline */}
      {last30.length > 0 && (
        <Plot
          data={[
            {
              x: last30.map((d) => d.date),
              y: last30.map((d) => d.price),
              type: 'scatter',
              mode: 'lines',
              fill: 'tozeroy',
              fillcolor: 'rgba(15, 118, 110, 0.1)',
              line: { color: '#0f766e', width: 2 },
              hovertemplate: 'Fecha: %{x}<br>WTI: $%{y:.2f}<extra></extra>',
            },
          ]}
          layout={{
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            font: { color: '#94a3b8', size: 10 },
            margin: { l: 35, r: 10, t: 5, b: 25 },
            height: 120,
            xaxis: {
              showgrid: false,
              tickformat: '%d/%m',
              nticks: 5,
            },
            yaxis: {
              showgrid: true,
              gridcolor: '#1e293b',
              nticks: 3,
            },
            hovermode: 'x',
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%', height: '120px' }}
        />
      )}

      {/* Impacto */}
      <div className="mt-3 p-3 bg-slate-800/30 rounded-lg border border-slate-700/50">
        <p className="text-xs text-slate-400">
          <span className="text-petroleo-400 font-medium">Impacto estimado: </span>
          {data.current > 80
            ? 'Con el WTI por encima de $80, es probable que los precios de combustibles en Ecuador se mantengan o suban en el proximo ajuste.'
            : data.current > 60
            ? 'Con el WTI en un rango moderado, los precios de combustibles podrian mantenerse estables.'
            : 'Con el WTI en niveles bajos, existe posibilidad de reduccion en los precios de combustibles.'}
        </p>
      </div>
    </div>
  );
}
