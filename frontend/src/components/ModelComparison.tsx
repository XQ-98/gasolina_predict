'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { Eye, EyeOff } from 'lucide-react';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface ModelComparisonProps {
  prediction: PredictionResult;
  historicalData: HistoricalPrice[];
  fuelType: string;
}

const modelConfig = {
  sarima: {
    name: 'SARIMA',
    color: '#3b82f6',
    description: 'Modelo estadistico de series temporales con estacionalidad mensual',
  },
  xgboost: {
    name: 'XGBoost',
    color: '#10b981',
    description: 'Gradient boosting con variables exogenas (WTI, bandas, tendencia)',
  },
  lstm: {
    name: 'LSTM',
    color: '#8b5cf6',
    description: 'Red neuronal recurrente para patrones secuenciales complejos',
  },
  ensemble: {
    name: 'Ensemble',
    color: '#ef4444',
    description: 'Combinacion ponderada de los 3 modelos segun desempeno',
  },
};

const fuelKeys: Record<string, keyof HistoricalPrice> = {
  extra: 'extra',
  ecopais: 'ecopais',
  super_95: 'super_95',
  diesel: 'diesel',
};

export default function ModelComparison({
  prediction,
  historicalData,
  fuelType,
}: ModelComparisonProps) {
  const [activeModels, setActiveModels] = useState<Record<string, boolean>>({
    sarima: true,
    xgboost: true,
    lstm: true,
    ensemble: true,
  });

  const toggleModel = (model: string) => {
    setActiveModels((prev) => ({ ...prev, [model]: !prev[model] }));
  };

  const models = prediction.models;
  if (!models) return null;

  // Ultimos 12 meses historicos
  const recent = historicalData.slice(-12);
  const recentDates = recent.map((d) => d.date);
  const fuelKey = fuelKeys[fuelType] || 'extra';
  const recentPrices = recent.map((d) => (d as any)[fuelKey] as number);

  const traces: any[] = [];

  // Historico
  traces.push({
    x: recentDates,
    y: recentPrices,
    type: 'scatter',
    mode: 'lines+markers',
    name: 'Historico',
    line: { color: '#94a3b8', width: 2 },
    marker: { size: 4 },
  });

  // Modelos individuales
  if (activeModels.sarima && models.sarima) {
    traces.push({
      x: models.dates,
      y: models.sarima,
      type: 'scatter',
      mode: 'lines',
      name: 'SARIMA',
      line: { color: modelConfig.sarima.color, width: 2, dash: 'dot' },
    });
  }
  if (activeModels.xgboost && models.xgboost) {
    traces.push({
      x: models.dates,
      y: models.xgboost,
      type: 'scatter',
      mode: 'lines',
      name: 'XGBoost',
      line: { color: modelConfig.xgboost.color, width: 2, dash: 'dot' },
    });
  }
  if (activeModels.lstm && models.lstm) {
    traces.push({
      x: models.dates,
      y: models.lstm,
      type: 'scatter',
      mode: 'lines',
      name: 'LSTM',
      line: { color: modelConfig.lstm.color, width: 2, dash: 'dot' },
    });
  }
  if (activeModels.ensemble && models.ensemble) {
    traces.push({
      x: models.dates,
      y: models.ensemble,
      type: 'scatter',
      mode: 'lines',
      name: 'Ensemble',
      line: { color: modelConfig.ensemble.color, width: 3 },
    });

    // Intervalo de confianza
    if (prediction.confidence_intervals && prediction.confidence_intervals.length > 0) {
      const ciDates = prediction.confidence_intervals.map((ci) => ci.date);
      traces.push({
        x: [...ciDates, ...ciDates.slice().reverse()],
        y: [
          ...prediction.confidence_intervals.map((ci) => ci.upper),
          ...prediction.confidence_intervals.slice().reverse().map((ci) => ci.lower),
        ],
        fill: 'toself',
        fillcolor: 'rgba(239, 68, 68, 0.08)',
        line: { color: 'transparent' },
        type: 'scatter',
        name: 'IC 95% Ensemble',
        showlegend: false,
      });
    }
  }

  const lastHistDate = recentDates[recentDates.length - 1];

  return (
    <div className="space-y-4">
      {/* Toggles de modelos */}
      <div className="flex flex-wrap gap-3">
        {Object.entries(modelConfig).map(([key, config]) => {
          const isActive = activeModels[key];
          const weight = key !== 'ensemble' && models.weights ? models.weights[key] : null;
          const metric = key !== 'ensemble' && prediction.metrics ? prediction.metrics[key] : null;

          return (
            <button
              key={key}
              onClick={() => toggleModel(key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${
                isActive
                  ? 'border-slate-600 bg-slate-800'
                  : 'border-slate-800 bg-slate-900/50 opacity-50'
              }`}
            >
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: isActive ? config.color : '#475569' }}
              />
              <div className="text-left">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-medium ${isActive ? 'text-white' : 'text-slate-500'}`}>
                    {config.name}
                  </span>
                  {isActive ? (
                    <Eye className="w-3 h-3 text-slate-500" />
                  ) : (
                    <EyeOff className="w-3 h-3 text-slate-600" />
                  )}
                </div>
                {weight != null && (
                  <span className="text-xs text-slate-500">
                    Peso: {(weight * 100).toFixed(1)}%
                    {metric && !metric.error && ` | MAPE: ${metric.mape.toFixed(1)}%`}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Grafico */}
      <Plot
        data={traces}
        layout={{
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          font: { color: '#94a3b8', size: 11 },
          margin: { l: 60, r: 20, t: 20, b: 40 },
          height: 450,
          xaxis: {
            gridcolor: '#1e293b',
            tickformat: '%b %Y',
          },
          yaxis: {
            gridcolor: '#1e293b',
            title: { text: 'Precio (USD/galon)', font: { size: 11 } },
          },
          legend: {
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.02,
            xanchor: 'left',
            x: 0,
            font: { size: 10 },
          },
          shapes: lastHistDate
            ? [
                {
                  type: 'line',
                  x0: lastHistDate,
                  x1: lastHistDate,
                  y0: 0,
                  y1: 1,
                  yref: 'paper',
                  line: { color: '#475569', width: 1, dash: 'dot' },
                },
              ]
            : [],
          annotations: lastHistDate
            ? [
                {
                  x: lastHistDate,
                  y: 1,
                  yref: 'paper',
                  text: 'Inicio prediccion',
                  showarrow: false,
                  font: { size: 10, color: '#64748b' },
                  yanchor: 'bottom',
                },
              ]
            : [],
          hovermode: 'x unified',
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
      />

      {/* Tabla de metricas */}
      {prediction.metrics && models.weights && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-2 px-3 text-slate-500 font-medium">Modelo</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium">Peso</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium">RMSE</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium">MAE</th>
                <th className="text-right py-2 px-3 text-slate-500 font-medium">MAPE</th>
              </tr>
            </thead>
            <tbody>
              {(['sarima', 'xgboost', 'lstm'] as const).map((key) => {
                const config = modelConfig[key];
                const m = prediction.metrics[key];
                const weight = models.weights[key];

                return (
                  <tr key={key} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                        <span className="text-white font-medium">{config.name}</span>
                      </div>
                    </td>
                    <td className="text-right py-2 px-3 text-slate-300">
                      {weight != null ? `${(weight * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="text-right py-2 px-3 text-slate-300">
                      {m && !m.error ? `$${m.rmse.toFixed(4)}` : '-'}
                    </td>
                    <td className="text-right py-2 px-3 text-slate-300">
                      {m && !m.error ? `$${m.mae.toFixed(4)}` : '-'}
                    </td>
                    <td className="text-right py-2 px-3">
                      {m && !m.error ? (
                        <span
                          className={
                            m.mape < 3
                              ? 'text-emerald-400'
                              : m.mape < 8
                              ? 'text-yellow-400'
                              : 'text-red-400'
                          }
                        >
                          {m.mape.toFixed(1)}%
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                );
              })}
              <tr className="bg-slate-800/30 font-semibold">
                <td className="py-2 px-3">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: modelConfig.ensemble.color }} />
                    <span className="text-white">Ensemble</span>
                  </div>
                </td>
                <td className="text-right py-2 px-3 text-white">100%</td>
                <td className="text-right py-2 px-3 text-slate-400" colSpan={2}>
                  Combinacion ponderada
                </td>
                <td className="text-right py-2 px-3 text-slate-400">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Descripciones */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {(['sarima', 'xgboost', 'lstm'] as const).map((key) => {
          const config = modelConfig[key];
          return (
            <div key={key} className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                <span className="text-sm font-medium text-white">{config.name}</span>
              </div>
              <p className="text-xs text-slate-500">{config.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
