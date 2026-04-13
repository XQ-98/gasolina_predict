'use client';

import { useState, useEffect } from 'react';
import { History, CheckCircle, XCircle, Clock, TrendingUp, TrendingDown, RefreshCw, Loader2, Award } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const fuelLabels: Record<string, string> = {
  extra: 'Extra',
  ecopais: 'EcoPais',
  super_95: 'Super 95',
  diesel: 'Diesel',
};

const fuelColors: Record<string, string> = {
  extra: 'text-teal-400',
  ecopais: 'text-lime-400',
  super_95: 'text-amber-400',
  diesel: 'text-red-400',
};

interface FuelPrediction {
  fuel_type: string;
  previous_price: number | null;
  predicted_price: number;
  actual_price: number | null;
  accuracy_pct: number | null;
  band_status: string | null;
  wti_predicted: number | null;
  is_correct: boolean | null;
  predicted_at: string | null;
}

interface DateGroup {
  target_date: string;
  fuels: FuelPrediction[];
}

interface Stats {
  total_predictions: number;
  total_with_actual: number;
  total_pending: number;
  total_correct: number;
  avg_accuracy_pct: number | null;
  hit_rate_pct: number | null;
}

interface Scorecard {
  dates: DateGroup[];
  stats: Stats;
}

export default function PredictionHistory() {
  const [data, setData] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScorecard = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/predictions/scorecard`);
      if (!res.ok) throw new Error('Error al obtener scorecard');
      const d = await res.json();
      setData(d);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const updateActuals = async () => {
    setUpdating(true);
    try {
      const res = await fetch(`${API_BASE}/api/predictions/update-actuals`, { method: 'POST' });
      if (!res.ok) throw new Error('Error al actualizar');
      await loadScorecard();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUpdating(false);
    }
  };

  useEffect(() => {
    loadScorecard();
  }, []);

  if (loading) {
    return (
      <div className="card flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
        <span className="text-sm text-slate-400 ml-2">Cargando historial...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <p className="text-sm text-red-400">Error: {error}</p>
        <button onClick={loadScorecard} className="btn-primary mt-3 text-sm">Reintentar</button>
      </div>
    );
  }

  if (!data || data.dates.length === 0) {
    return (
      <div className="card text-center py-12">
        <History className="w-12 h-12 text-slate-600 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-white mb-2">Sin predicciones aun</h3>
        <p className="text-sm text-slate-400">
          Las predicciones que hagas en la pestana &quot;Prediccion&quot; apareceran aqui
          con su comparativa de precision cuando se conozcan los precios reales.
        </p>
      </div>
    );
  }

  const stats = data.stats;

  return (
    <div className="space-y-6">
      {/* Stats globales */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="card text-center">
          <span className="text-xs text-slate-500 block">Predicciones</span>
          <span className="text-2xl font-bold text-white">{stats.total_predictions}</span>
        </div>
        <div className="card text-center">
          <span className="text-xs text-slate-500 block">Con precio real</span>
          <span className="text-2xl font-bold text-emerald-400">{stats.total_with_actual}</span>
        </div>
        <div className="card text-center">
          <span className="text-xs text-slate-500 block">Pendientes</span>
          <span className="text-2xl font-bold text-yellow-400">{stats.total_pending}</span>
        </div>
        <div className="card text-center">
          <span className="text-xs text-slate-500 block">Precision media</span>
          <span className={`text-2xl font-bold ${
            stats.avg_accuracy_pct != null && stats.avg_accuracy_pct >= 95
              ? 'text-emerald-400'
              : stats.avg_accuracy_pct != null && stats.avg_accuracy_pct >= 90
              ? 'text-yellow-400'
              : 'text-slate-400'
          }`}>
            {stats.avg_accuracy_pct != null ? `${stats.avg_accuracy_pct}%` : '-'}
          </span>
        </div>
        <div className="card text-center">
          <span className="text-xs text-slate-500 block">Tasa de acierto</span>
          <span className={`text-2xl font-bold ${
            stats.hit_rate_pct != null && stats.hit_rate_pct >= 80
              ? 'text-emerald-400'
              : stats.hit_rate_pct != null && stats.hit_rate_pct >= 60
              ? 'text-yellow-400'
              : 'text-slate-400'
          }`}>
            {stats.hit_rate_pct != null ? `${stats.hit_rate_pct}%` : '-'}
          </span>
          <span className="text-xs text-slate-600 block">(&lt;2% error)</span>
        </div>
      </div>

      {/* Boton actualizar */}
      {stats.total_pending > 0 && (
        <div className="flex items-center gap-3">
          <button
            onClick={updateActuals}
            disabled={updating}
            className="btn-primary text-sm flex items-center gap-2"
          >
            {updating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Actualizar precios reales
          </button>
          <span className="text-xs text-slate-500">
            {stats.total_pending} prediccion{stats.total_pending !== 1 ? 'es' : ''} pendiente{stats.total_pending !== 1 ? 's' : ''} de verificar
          </span>
        </div>
      )}

      {/* Tabla por fecha */}
      {data.dates.map((dateGroup) => {
        const isPast = new Date(dateGroup.target_date) <= new Date();
        const allHaveActual = dateGroup.fuels.every((f) => f.actual_price != null);
        const someHaveActual = dateGroup.fuels.some((f) => f.actual_price != null);

        return (
          <div key={dateGroup.target_date} className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  allHaveActual
                    ? 'bg-emerald-900/30'
                    : isPast
                    ? 'bg-yellow-900/30'
                    : 'bg-slate-800'
                }`}>
                  {allHaveActual ? (
                    <Award className="w-5 h-5 text-emerald-400" />
                  ) : isPast ? (
                    <Clock className="w-5 h-5 text-yellow-400" />
                  ) : (
                    <Clock className="w-5 h-5 text-slate-500" />
                  )}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Prediccion para el {dateGroup.target_date}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {allHaveActual
                      ? 'Verificada - precios reales disponibles'
                      : isPast
                      ? 'Pendiente de verificar precios reales'
                      : 'Prediccion futura'}
                  </p>
                </div>
              </div>
            </div>

            {/* Tabla de combustibles */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-2 px-3 text-slate-500 font-medium">Combustible</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Precio anterior</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Predicho</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Real</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Error</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Precision</th>
                    <th className="text-center py-2 px-3 text-slate-500 font-medium">Banda</th>
                    <th className="text-center py-2 px-3 text-slate-500 font-medium">Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {dateGroup.fuels.map((fuel, i) => {
                    const errorAbs = fuel.actual_price != null
                      ? Math.abs(fuel.predicted_price - fuel.actual_price)
                      : null;
                    const realChange = fuel.actual_price != null && fuel.previous_price != null && fuel.previous_price > 0
                      ? ((fuel.actual_price - fuel.previous_price) / fuel.previous_price) * 100
                      : null;
                    const predChange = fuel.previous_price != null && fuel.previous_price > 0
                      ? ((fuel.predicted_price - fuel.previous_price) / fuel.previous_price) * 100
                      : null;

                    return (
                      <tr key={`${fuel.fuel_type}-${i}`} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="py-2 px-3">
                          <span className={`font-medium ${fuelColors[fuel.fuel_type] || 'text-slate-300'}`}>
                            {fuelLabels[fuel.fuel_type] || fuel.fuel_type}
                          </span>
                        </td>
                        <td className="text-right py-2 px-3 text-slate-400">
                          {fuel.previous_price != null ? (
                            `$${fuel.previous_price.toFixed(3)}`
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="text-right py-2 px-3">
                          <span className="text-white font-medium">${fuel.predicted_price.toFixed(3)}</span>
                          {predChange != null && (
                            <span className={`block text-xs ${predChange > 0 ? 'text-red-500' : predChange < 0 ? 'text-emerald-500' : 'text-slate-500'}`}>
                              {predChange > 0 ? '+' : ''}{predChange.toFixed(1)}%
                            </span>
                          )}
                        </td>
                        <td className="text-right py-2 px-3">
                          {fuel.actual_price != null ? (
                            <>
                              <span className="text-white font-medium">${fuel.actual_price.toFixed(3)}</span>
                              {realChange != null && (
                                <span className={`block text-xs ${realChange > 0 ? 'text-red-500' : realChange < 0 ? 'text-emerald-500' : 'text-slate-500'}`}>
                                  {realChange > 0 ? '+' : ''}{realChange.toFixed(1)}%
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="text-slate-600 italic">Pendiente</span>
                          )}
                        </td>
                        <td className="text-right py-2 px-3">
                          {errorAbs != null ? (
                            <span className={errorAbs < 0.05 ? 'text-emerald-400' : 'text-red-400'}>
                              ${errorAbs.toFixed(3)}
                            </span>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="text-right py-2 px-3">
                          {fuel.accuracy_pct != null ? (
                            <span className={`font-bold ${
                              fuel.accuracy_pct >= 98
                                ? 'text-emerald-400'
                                : fuel.accuracy_pct >= 95
                                ? 'text-yellow-400'
                                : 'text-red-400'
                            }`}>
                              {fuel.accuracy_pct.toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="text-center py-2 px-3">
                          {fuel.band_status ? (
                            <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                              fuel.band_status === 'TECHO'
                                ? 'bg-red-900/30 text-red-400'
                                : fuel.band_status === 'PISO'
                                ? 'bg-emerald-900/30 text-emerald-400'
                                : fuel.band_status === 'LIBRE'
                                ? 'bg-amber-900/30 text-amber-400'
                                : 'bg-slate-800 text-slate-400'
                            }`}>
                              {fuel.band_status}
                            </span>
                          ) : (
                            <span className="text-slate-600">-</span>
                          )}
                        </td>
                        <td className="text-center py-2 px-3">
                          {fuel.is_correct === true ? (
                            <CheckCircle className="w-5 h-5 text-emerald-400 mx-auto" />
                          ) : fuel.is_correct === false ? (
                            <XCircle className="w-5 h-5 text-red-400 mx-auto" />
                          ) : (
                            <Clock className="w-4 h-4 text-slate-600 mx-auto" />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Nota de prediccion */}
            {dateGroup.fuels[0]?.predicted_at && (
              <p className="text-xs text-slate-600 mt-3">
                Prediccion realizada el {new Date(dateGroup.fuels[0].predicted_at).toLocaleDateString('es-EC')}
              </p>
            )}
          </div>
        );
      })}

      {/* Leyenda */}
      <div className="card">
        <h4 className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">Leyenda</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span>Acerto: error menor al 2%</span>
          </div>
          <div className="flex items-center gap-2">
            <XCircle className="w-4 h-4 text-red-400" />
            <span>Fallo: error mayor al 2%</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-600" />
            <span>Pendiente: esperando precio real</span>
          </div>
        </div>
      </div>
    </div>
  );
}
