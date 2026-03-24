'use client';

import { useState, useEffect } from 'react';
import { Sliders, Fuel, Loader2, Info } from 'lucide-react';
import dynamic from 'next/dynamic';
import { fetchBandSimulation } from '@/lib/api';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

const fuelOptions = [
  { value: 'extra', label: 'Extra' },
  { value: 'ecopais', label: 'EcoPais' },
  { value: 'super_95', label: 'Super 95' },
  { value: 'diesel', label: 'Diesel' },
];

export default function BandSimulator() {
  const [wtiPrice, setWtiPrice] = useState(75);
  const [fuelType, setFuelType] = useState('extra');
  const [simulation, setSimulation] = useState<BandSimulation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchBandSimulation(wtiPrice, fuelType);
      setSimulation(result);
    } catch (e: any) {
      setError(e.message);
      // Simulacion local como fallback
      const currentPrice = fuelType === 'extra' ? 2.722 : fuelType === 'ecopais' ? 2.722 : fuelType === 'super_95' ? 3.806 : 1.871;
      const theoreticalChange = ((wtiPrice - 70) / 70) * 0.15;
      const theoreticalPrice = currentPrice * (1 + theoreticalChange);
      const maxPossible = currentPrice * 1.05;
      const minPossible = currentPrice * 0.90;
      const bandResult = Math.max(minPossible, Math.min(maxPossible, theoreticalPrice));
      const bandStatus: 'TECHO' | 'PISO' | 'DENTRO' =
        bandResult >= maxPossible ? 'TECHO' : bandResult <= minPossible ? 'PISO' : 'DENTRO';

      setSimulation({
        current_price: currentPrice,
        theoretical_price: theoreticalPrice,
        band_result: bandResult,
        band_status: bandStatus,
        max_possible: maxPossible,
        min_possible: minPossible,
        wti_price: wtiPrice,
      });
      setError(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSimulation();
  }, [wtiPrice, fuelType]);

  const statusColors: Record<string, { bg: string; text: string; label: string }> = {
    TECHO: { bg: 'bg-red-900/20', text: 'text-red-400', label: 'Se aplica techo (+5%)' },
    PISO: { bg: 'bg-emerald-900/20', text: 'text-emerald-400', label: 'Se aplica piso (-10%)' },
    DENTRO: { bg: 'bg-gasolina-900/20', text: 'text-gasolina-400', label: 'Dentro de la banda' },
  };

  return (
    <div className="space-y-6">
      {/* Controles */}
      <div className="card">
        <h3 className="card-header flex items-center gap-2">
          <Sliders className="w-5 h-5 text-petroleo-400" />
          Simulador del Sistema de Bandas
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Slider WTI */}
          <div>
            <label className="text-sm text-slate-400 block mb-2">
              Precio del WTI (USD/barril)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={40}
                max={130}
                step={0.5}
                value={wtiPrice}
                onChange={(e) => setWtiPrice(parseFloat(e.target.value))}
                className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-petroleo-600"
              />
              <div className="w-20">
                <input
                  type="number"
                  min={40}
                  max={130}
                  step={0.5}
                  value={wtiPrice}
                  onChange={(e) => setWtiPrice(parseFloat(e.target.value) || 70)}
                  className="select-custom w-full text-center text-sm"
                />
              </div>
            </div>
            <div className="flex justify-between text-xs text-slate-600 mt-1">
              <span>$40</span>
              <span>$70</span>
              <span>$100</span>
              <span>$130</span>
            </div>
          </div>

          {/* Selector de combustible */}
          <div>
            <label className="text-sm text-slate-400 block mb-2">Tipo de combustible</label>
            <div className="flex gap-2 flex-wrap">
              {fuelOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setFuelType(opt.value)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    fuelType === opt.value
                      ? 'bg-petroleo-700 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Resultado */}
      {loading ? (
        <div className="card flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
        </div>
      ) : simulation ? (
        <div className="space-y-4">
          {/* Estado de la banda */}
          <div className={`card border ${
            simulation.band_status === 'TECHO'
              ? 'border-red-800'
              : simulation.band_status === 'PISO'
              ? 'border-emerald-800'
              : 'border-gasolina-700'
          }`}>
            <div className={`rounded-lg p-4 ${statusColors[simulation.band_status]?.bg || ''}`}>
              <h4 className={`text-lg font-bold ${statusColors[simulation.band_status]?.text || 'text-white'}`}>
                {statusColors[simulation.band_status]?.label || 'Estado desconocido'}
              </h4>
              <p className="text-sm text-slate-400 mt-1">
                Con WTI a ${wtiPrice.toFixed(2)}/barril
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <div>
                <span className="text-xs text-slate-500 block">Precio actual</span>
                <span className="text-lg font-semibold text-white">
                  ${simulation.current_price.toFixed(3)}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Precio teorico</span>
                <span className="text-lg font-semibold text-slate-300">
                  ${simulation.theoretical_price.toFixed(3)}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Resultado con banda</span>
                <span className={`text-lg font-semibold ${statusColors[simulation.band_status]?.text || 'text-white'}`}>
                  ${simulation.band_result.toFixed(3)}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Cambio</span>
                <span className={`text-lg font-semibold ${
                  simulation.band_result > simulation.current_price ? 'text-red-400' : 'text-emerald-400'
                }`}>
                  {simulation.band_result > simulation.current_price ? '+' : ''}
                  {((simulation.band_result - simulation.current_price) / simulation.current_price * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          {/* Grafico de banda visual */}
          <div className="card">
            <h4 className="text-sm font-semibold text-white mb-4">Visualizacion de la Banda</h4>
            <Plot
              data={[
                // Barra de piso
                {
                  x: ['Banda'],
                  y: [simulation.min_possible],
                  type: 'bar',
                  name: `Piso (-10%): $${simulation.min_possible.toFixed(3)}`,
                  marker: { color: '#22c55e', opacity: 0.3 },
                  width: [0.6],
                  hovertemplate: 'Piso: $%{y:.3f}<extra></extra>',
                },
                // Barra de rango dentro
                {
                  x: ['Banda'],
                  y: [simulation.max_possible - simulation.min_possible],
                  type: 'bar',
                  name: 'Rango permitido',
                  marker: { color: '#f59e0b', opacity: 0.2 },
                  width: [0.6],
                  hoverinfo: 'skip',
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  ...({ base: [simulation.min_possible] } as any),
                },
              ]}
              layout={{
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#94a3b8', size: 11 },
                margin: { l: 60, r: 20, t: 10, b: 40 },
                height: 280,
                barmode: 'overlay',
                xaxis: { showgrid: false },
                yaxis: {
                  gridcolor: '#1e293b',
                  title: { text: 'USD/galon' },
                },
                shapes: [
                  // Linea del precio teorico
                  {
                    type: 'line',
                    x0: -0.4,
                    x1: 0.4,
                    y0: simulation.theoretical_price,
                    y1: simulation.theoretical_price,
                    line: { color: '#94a3b8', width: 2, dash: 'dot' },
                  },
                  // Linea del resultado
                  {
                    type: 'line',
                    x0: -0.4,
                    x1: 0.4,
                    y0: simulation.band_result,
                    y1: simulation.band_result,
                    line: { color: '#14b8a6', width: 3 },
                  },
                  // Linea del techo
                  {
                    type: 'line',
                    x0: -0.35,
                    x1: 0.35,
                    y0: simulation.max_possible,
                    y1: simulation.max_possible,
                    line: { color: '#ef4444', width: 2, dash: 'dash' },
                  },
                  // Linea del piso
                  {
                    type: 'line',
                    x0: -0.35,
                    x1: 0.35,
                    y0: simulation.min_possible,
                    y1: simulation.min_possible,
                    line: { color: '#22c55e', width: 2, dash: 'dash' },
                  },
                ],
                annotations: [
                  {
                    x: 0.45,
                    y: simulation.max_possible,
                    text: `Techo: $${simulation.max_possible.toFixed(3)}`,
                    showarrow: false,
                    font: { color: '#ef4444', size: 10 },
                    xanchor: 'left',
                  },
                  {
                    x: 0.45,
                    y: simulation.min_possible,
                    text: `Piso: $${simulation.min_possible.toFixed(3)}`,
                    showarrow: false,
                    font: { color: '#22c55e', size: 10 },
                    xanchor: 'left',
                  },
                  {
                    x: 0.45,
                    y: simulation.band_result,
                    text: `Resultado: $${simulation.band_result.toFixed(3)}`,
                    showarrow: false,
                    font: { color: '#14b8a6', size: 11, },
                    xanchor: 'left',
                  },
                  {
                    x: -0.45,
                    y: simulation.theoretical_price,
                    text: `Teorico: $${simulation.theoretical_price.toFixed(3)}`,
                    showarrow: false,
                    font: { color: '#94a3b8', size: 10 },
                    xanchor: 'right',
                  },
                ],
                showlegend: false,
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: '100%', height: '280px' }}
            />
          </div>

          {/* Tabla de desglose */}
          <div className="card">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Info className="w-4 h-4 text-petroleo-400" />
              Desglose de la formula
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-2 px-3 text-slate-500 font-medium">Componente</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Valor estimado</th>
                  </tr>
                </thead>
                <tbody>
                  {(simulation.formula_breakdown ? [
                    { label: 'Costo de importacion (CIF)', value: simulation.formula_breakdown.import_cost_gallon ?? 0 },
                    { label: 'Transporte', value: simulation.formula_breakdown.transport_cost ?? 0 },
                    { label: 'Almacenamiento', value: simulation.formula_breakdown.storage_cost ?? 0 },
                    { label: 'Margen Petroecuador (EP)', value: simulation.formula_breakdown.petroecuador_margin ?? 0 },
                    { label: 'Costo de capital', value: simulation.formula_breakdown.capital_cost ?? 0 },
                    { label: 'IVA (15%)', value: simulation.formula_breakdown.iva_amount ?? 0 },
                    { label: 'Margen de comercializacion', value: simulation.formula_breakdown.commercial_margin ?? 0 },
                    { label: 'IVA comercializacion', value: simulation.formula_breakdown.commercial_margin_iva ?? 0 },
                  ] : [
                    { label: 'Precio teorico (sin desglose)', value: simulation.theoretical_price },
                  ]).map((row) => (
                    <tr key={row.label} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="py-2 px-3 text-slate-300">{row.label}</td>
                      <td className="text-right py-2 px-3 text-slate-300">${row.value.toFixed(3)}</td>
                    </tr>
                  ))}
                  <tr className="bg-slate-800/30 font-semibold">
                    <td className="py-2 px-3 text-white">Total (precio teorico)</td>
                    <td className="text-right py-2 px-3 text-white">
                      ${simulation.theoretical_price.toFixed(3)}
                    </td>
                  </tr>
                  <tr className="bg-petroleo-900/20 font-semibold">
                    <td className="py-2 px-3 text-petroleo-400">Precio final (con banda)</td>
                    <td className="text-right py-2 px-3 text-petroleo-400">
                      ${simulation.band_result.toFixed(3)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}

      {/* Explicacion */}
      <div className="card bg-slate-800/30">
        <h4 className="text-sm font-semibold text-white mb-2">¿Como funciona el sistema de bandas?</h4>
        <div className="space-y-2 text-sm text-slate-400">
          <p>
            Desde julio de 2020, Ecuador aplica un sistema de bandas para ajustar los precios
            de los combustibles mensualmente (cada dia 11).
          </p>
          <p>
            <span className="text-red-400 font-medium">Techo (+5%): </span>
            El precio no puede subir mas del 5% respecto al mes anterior.
          </p>
          <p>
            <span className="text-emerald-400 font-medium">Piso (-10%): </span>
            El precio no puede bajar mas del 10% respecto al mes anterior.
          </p>
          <p>
            <span className="text-gasolina-400 font-medium">Dentro: </span>
            Si el precio teorico esta dentro de la banda, se aplica tal cual.
          </p>
        </div>
      </div>
    </div>
  );
}
