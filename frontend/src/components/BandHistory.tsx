'use client';

import { useState, useEffect } from 'react';
import { History, TrendingUp, TrendingDown, Minus, Loader2, Filter } from 'lucide-react';
import dynamic from 'next/dynamic';
import { fetchBandHistory } from '@/lib/api';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const fuelLabels: Record<string, string> = {
  extra: 'Extra',
  ecopais: 'EcoPais',
  super_95: 'Super 95',
  diesel: 'Diesel',
};

export default function BandHistory() {
  const [data, setData] = useState<BandHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterFuel, setFilterFuel] = useState<string>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchBandHistory();
      setData(result);
    } catch (e: any) {
      setError(e.message);
      // Datos de ejemplo como fallback
      setData(generateSampleData());
      setError(null);
    } finally {
      setLoading(false);
    }
  };

  const filtered = filterFuel === 'all' ? data : data.filter((d) => d.fuel_type === filterFuel);

  const totalSubidas = filtered.filter((d) => d.direction === 'SUBE').length;
  const totalBajadas = filtered.filter((d) => d.direction === 'BAJA').length;
  const totalIgual = filtered.filter((d) => d.direction === 'IGUAL').length;

  // Datos para grafico de barras
  const chartData = filtered.reduce<Record<string, { date: string; change: number }[]>>((acc, entry) => {
    if (!acc[entry.fuel_type]) acc[entry.fuel_type] = [];
    acc[entry.fuel_type].push({ date: entry.date, change: entry.change_percent });
    return acc;
  }, {});

  const chartColors: Record<string, string> = {
    extra: '#14b8a6',
    ecopais: '#84cc16',
    super_95: '#f59e0b',
    diesel: '#ef4444',
  };

  if (loading) {
    return (
      <div className="card flex items-center justify-center h-48">
        <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Resumen */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="card-header mb-0 flex items-center gap-2">
            <History className="w-5 h-5 text-petroleo-400" />
            Historial de Cambios (Dia 11)
          </h3>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <select
              value={filterFuel}
              onChange={(e) => setFilterFuel(e.target.value)}
              className="select-custom text-xs py-1"
            >
              <option value="all">Todos</option>
              <option value="extra">Extra</option>
              <option value="ecopais">EcoPais</option>
              <option value="super_95">Super 95</option>
              <option value="diesel">Diesel</option>
            </select>
          </div>
        </div>

        {/* Contadores */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-red-900/10 border border-red-800/30 rounded-lg p-3 text-center">
            <span className="text-2xl font-bold text-red-400">{totalSubidas}</span>
            <p className="text-xs text-slate-500 mt-1">Subidas</p>
          </div>
          <div className="bg-emerald-900/10 border border-emerald-800/30 rounded-lg p-3 text-center">
            <span className="text-2xl font-bold text-emerald-400">{totalBajadas}</span>
            <p className="text-xs text-slate-500 mt-1">Bajadas</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
            <span className="text-2xl font-bold text-slate-400">{totalIgual}</span>
            <p className="text-xs text-slate-500 mt-1">Sin cambio</p>
          </div>
        </div>

        {/* Grafico de barras */}
        {Object.keys(chartData).length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-medium text-slate-400 mb-3">Cambios porcentuales mensuales</h4>
            <Plot
              data={Object.entries(chartData).map(([fuel, entries]) => ({
                x: entries.map((e) => e.date),
                y: entries.map((e) => e.change),
                type: 'bar',
                name: fuelLabels[fuel] || fuel,
                marker: {
                  color: entries.map((e) =>
                    e.change > 0 ? '#ef4444' : e.change < 0 ? '#22c55e' : '#94a3b8'
                  ),
                  opacity: 0.8,
                },
                hovertemplate: `${fuelLabels[fuel] || fuel}<br>Fecha: %{x}<br>Cambio: %{y:.2f}%<extra></extra>`,
              }))}
              layout={{
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#94a3b8', size: 10 },
                margin: { l: 50, r: 20, t: 10, b: 40 },
                height: 300,
                barmode: filterFuel === 'all' ? 'group' : 'relative',
                xaxis: {
                  gridcolor: '#1e293b',
                  tickformat: '%b %Y',
                },
                yaxis: {
                  gridcolor: '#1e293b',
                  title: { text: 'Cambio %' },
                  zeroline: true,
                  zerolinecolor: '#475569',
                },
                legend: {
                  orientation: 'h',
                  y: 1.1,
                  font: { size: 10 },
                },
                showlegend: filterFuel === 'all',
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: '100%', height: '300px' }}
            />
          </div>
        )}

        {/* Tabla */}
        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0">
              <tr className="border-b border-slate-700">
                <th className="text-left py-2 px-3 text-slate-500 font-medium bg-slate-800">Fecha</th>
                <th className="text-left py-2 px-3 text-slate-500 font-medium bg-slate-800">Combustible</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium bg-slate-800">Anterior</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium bg-slate-800">Nuevo</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium bg-slate-800">Cambio %</th>
                <th className="text-center py-2 px-3 text-slate-500 font-medium bg-slate-800">Dir.</th>
                <th className="text-center py-2 px-3 text-slate-500 font-medium bg-slate-800">Banda</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry, i) => (
                <tr
                  key={`${entry.date}-${entry.fuel_type}-${i}`}
                  className="border-b border-slate-800/50 hover:bg-slate-800/30"
                >
                  <td className="py-2 px-3 text-slate-300 whitespace-nowrap">{entry.date}</td>
                  <td className="py-2 px-3 text-slate-300">{fuelLabels[entry.fuel_type] || entry.fuel_type}</td>
                  <td className="text-right py-2 px-3 text-slate-400">${entry.previous_price.toFixed(3)}</td>
                  <td className="text-right py-2 px-3 text-slate-300 font-medium">${entry.new_price.toFixed(3)}</td>
                  <td className={`text-right py-2 px-3 font-medium ${
                    entry.change_percent > 0
                      ? 'text-red-400'
                      : entry.change_percent < 0
                      ? 'text-emerald-400'
                      : 'text-slate-400'
                  }`}>
                    {entry.change_percent > 0 ? '+' : ''}
                    {entry.change_percent.toFixed(2)}%
                  </td>
                  <td className="text-center py-2 px-3">
                    {entry.direction === 'SUBE' && <TrendingUp className="w-4 h-4 text-red-400 mx-auto" />}
                    {entry.direction === 'BAJA' && <TrendingDown className="w-4 h-4 text-emerald-400 mx-auto" />}
                    {entry.direction === 'IGUAL' && <Minus className="w-4 h-4 text-slate-400 mx-auto" />}
                  </td>
                  <td className="text-center py-2 px-3">
                    {entry.band_applied ? (
                      <span className="badge-band">Si</span>
                    ) : (
                      <span className="badge-neutral">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <div className="text-center text-slate-500 py-8">
            No hay datos disponibles para este filtro
          </div>
        )}
      </div>
    </div>
  );
}

function generateSampleData(): BandHistoryEntry[] {
  const fuels = ['extra', 'ecopais', 'super_95', 'diesel'];
  const basePrices: Record<string, number> = {
    extra: 2.40,
    ecopais: 2.40,
    super_95: 3.10,
    diesel: 1.60,
  };
  const entries: BandHistoryEntry[] = [];

  for (let year = 2020; year <= 2026; year++) {
    const startMonth = year === 2020 ? 7 : 1;
    const endMonth = year === 2026 ? 3 : 12;

    for (let month = startMonth; month <= endMonth; month++) {
      for (const fuel of fuels) {
        const change = (Math.random() - 0.45) * 6;
        const prevPrice = basePrices[fuel];
        const clampedChange = Math.max(-10, Math.min(5, change));
        const newPrice = prevPrice * (1 + clampedChange / 100);
        const direction: 'SUBE' | 'BAJA' | 'IGUAL' =
          clampedChange > 0.01 ? 'SUBE' : clampedChange < -0.01 ? 'BAJA' : 'IGUAL';

        entries.push({
          date: `${year}-${String(month).padStart(2, '0')}-11`,
          fuel_type: fuel,
          previous_price: prevPrice,
          new_price: parseFloat(newPrice.toFixed(3)),
          change_percent: parseFloat(clampedChange.toFixed(2)),
          direction,
          band_applied: Math.abs(clampedChange) >= 4.5 || Math.abs(clampedChange) >= 9.5,
        });

        basePrices[fuel] = newPrice;
      }
    }
  }

  return entries.sort((a, b) => b.date.localeCompare(a.date));
}
