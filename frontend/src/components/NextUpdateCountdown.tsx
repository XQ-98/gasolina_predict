'use client';

import { useState, useEffect } from 'react';
import { Clock, CalendarDays, Bell, TrendingUp, TrendingDown, Minus, Loader2, ChevronDown, ChevronUp, BarChart3, Calculator, Shield, RefreshCw } from 'lucide-react';
import Sigla from './Sigla';
import {
  differenceInDays,
  differenceInHours,
  differenceInMinutes,
  format,
  setDate,
  addMonths,
  isAfter,
  isSameDay,
  startOfDay,
} from 'date-fns';
import { es } from 'date-fns/locale';

interface ForecastDetail {
  wti_current: number;
  wti_predicted: number;
  wti_change_pct: number;
  wti_confidence: { lower: number; upper: number };
  wti_data_points: number;
  wti_weights: Record<string, number>;
  theoretical_price: number;
  formula_breakdown: Record<string, number>;
  band_status: string;
  max_price: number;
  min_price: number;
}

interface QuickForecast {
  fuel: string;
  label: string;
  current: number;
  estimated: number;
  change_pct: number;
  probability: 'alta' | 'media' | 'baja';
  direction: 'SUBE' | 'BAJA' | 'IGUAL';
  detail?: ForecastDetail;
}

const CACHE_KEY = 'gaspredict_forecast_cache';
// Cache valido por 2 horas (el WTI puede cambiar en el dia por eventos de mercado)
const CACHE_TTL_MS = 2 * 60 * 60 * 1000;

function loadCachedForecast(): QuickForecast[] | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const { ts, data } = JSON.parse(raw);
    if (Date.now() - ts < CACHE_TTL_MS) return data;
    localStorage.removeItem(CACHE_KEY);
  } catch { /* ignore */ }
  return null;
}

function saveForecastCache(data: QuickForecast[]) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data }));
  } catch { /* ignore */ }
}

function clearForecastCache() {
  try { localStorage.removeItem(CACHE_KEY); } catch { /* ignore */ }
}

async function fetchQuickForecast(): Promise<QuickForecast[]> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const fuels = ['extra', 'ecopais', 'diesel', 'super_95'];
  const results: QuickForecast[] = [];
  const labels: Record<string, string> = { extra: 'Extra', ecopais: 'EcoPais', diesel: 'Diesel', super_95: 'Super 95' };

  for (const fuel of fuels) {
    try {
      const res = await fetch(`${API_BASE}/api/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fuel_type: fuel, months: 1, approach: 'two_layer' }),
      });
      if (!res.ok) continue;
      const data = await res.json();
      const pred = data.predictions?.[0];
      if (!pred) continue;

      const current = data.current_price;
      const estimated = pred.price;
      const changePct = current > 0 ? ((estimated - current) / current) * 100 : 0;

      // Probabilidad basada en MAPE historico real por combustible
      // Extra/EcoPais/Diesel: formula determinista -> siempre Alta
      // Super 95: precio libre, modelo con MAPE ~3.6% -> siempre Media
      const freeMarket = fuel === 'super_95';
      const probability: 'alta' | 'media' | 'baja' = freeMarket ? 'media' : 'alta';

      // Extraer detalles de las 2 capas si existen
      const l1 = data.layer_1_wti?.detail || data.layer_1_wti;
      const l2 = data.layer_2_formula;
      const predDetail = data.predictions?.[0];

      const detail: ForecastDetail | undefined = l1 ? {
        wti_current: l1.wti_current ?? 0,
        wti_predicted: l1.wti_predicted_avg ?? 0,
        wti_change_pct: l1.wti_change_pct ?? 0,
        wti_confidence: l1.confidence_interval ?? { lower: 0, upper: 0 },
        wti_data_points: l1.data_points_used ?? 0,
        wti_weights: l1.weights ?? {},
        theoretical_price: l2?.theoretical_price ?? predDetail?.theoretical_price ?? 0,
        formula_breakdown: l2 ?? {},
        band_status: predDetail?.band_status ?? 'DENTRO',
        max_price: predDetail?.max_price ?? current * 1.05,
        min_price: predDetail?.min_price ?? current * 0.90,
      } : undefined;

      results.push({
        fuel,
        label: labels[fuel] || fuel,
        current: Math.round(current * 1000) / 1000,
        estimated: Math.round(estimated * 1000) / 1000,
        change_pct: Math.round(changePct * 100) / 100,
        probability,
        direction: changePct > 0.1 ? 'SUBE' : changePct < -0.1 ? 'BAJA' : 'IGUAL',
        detail,
      });
    } catch {
      // silently skip
    }
  }
  return results;
}

function getNextUpdateDate(now: Date): Date {
  const currentMonth11 = setDate(startOfDay(now), 11);

  if (isSameDay(now, currentMonth11)) {
    return currentMonth11;
  }

  if (isAfter(now, currentMonth11)) {
    return setDate(startOfDay(addMonths(now, 1)), 11);
  }

  return currentMonth11;
}

export default function NextUpdateCountdown() {
  const [now, setNow] = useState<Date | null>(null);
  const [forecast, setForecast] = useState<QuickForecast[]>([]);
  const [loadingForecast, setLoadingForecast] = useState(true);
  const [expandedFuel, setExpandedFuel] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    // Inicializar fecha solo en el cliente para evitar mismatch SSR
    setNow(new Date());
    const interval = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const cached = loadCachedForecast();
    if (cached && cached.length > 0) {
      setForecast(cached);
      setLoadingForecast(false);
      return;
    }
    fetchQuickForecast()
      .then((data) => { setForecast(data); saveForecastCache(data); })
      .catch(() => {})
      .finally(() => setLoadingForecast(false));
  }, []);

  function handleRefresh() {
    clearForecastCache();
    setRefreshing(true);
    setLoadingForecast(true);
    setForecast([]);
    fetchQuickForecast()
      .then((data) => { setForecast(data); saveForecastCache(data); })
      .catch(() => {})
      .finally(() => { setLoadingForecast(false); setRefreshing(false); });
  }

  // Mientras el cliente no hidrate, mostrar skeleton
  if (!now) {
    return (
      <div className="card animate-pulse">
        <div className="h-10 bg-slate-700/50 rounded w-1/2 mb-4" />
        <div className="h-2 bg-slate-700/50 rounded w-full mb-2" />
        <div className="h-2 bg-slate-700/50 rounded w-3/4" />
      </div>
    );
  }

  const nextUpdate = getNextUpdateDate(now);
  const isToday = isSameDay(now, nextUpdate);

  const totalDaysInRange = (() => {
    const prevMonth11 = setDate(startOfDay(addMonths(now, -1)), 11);
    const currentMonth11 = setDate(startOfDay(now), 11);
    if (isAfter(now, currentMonth11) || isSameDay(now, currentMonth11)) {
      return differenceInDays(setDate(startOfDay(addMonths(now, 1)), 11), currentMonth11);
    }
    return differenceInDays(currentMonth11, prevMonth11);
  })();

  const daysRemaining = differenceInDays(nextUpdate, startOfDay(now));
  const hoursRemaining = differenceInHours(nextUpdate, now) % 24;
  const minutesRemaining = differenceInMinutes(nextUpdate, now) % 60;

  const daysPassed = totalDaysInRange - daysRemaining;
  const progress = totalDaysInRange > 0 ? Math.min((daysPassed / totalDaysInRange) * 100, 100) : 0;

  if (isToday) {
    const dirColors = {
      SUBE: 'text-red-400',
      BAJA: 'text-emerald-400',
      IGUAL: 'text-slate-400',
    };

    return (
      <div className="card border-2 border-gasolina-500/50">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gasolina-500/20 flex items-center justify-center animate-pulse">
            <Bell className="w-6 h-6 text-gasolina-400" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">
              ¡Hoy se actualizan los precios!
            </h3>
            <p className="text-sm text-slate-400">
              {format(nextUpdate, "EEEE d 'de' MMMM, yyyy", { locale: es })}
            </p>
          </div>
        </div>
        <p className="text-sm text-gasolina-400 mt-3">
          Los nuevos precios de combustibles entran en vigencia hoy, dia 11.
        </p>

        {/* Prediccion del dia */}
        <div className="mt-4 pt-4 border-t border-gasolina-500/30">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs text-slate-500 uppercase tracking-wider font-medium">
              Prediccion para hoy
            </h4>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
              Recalcular
            </button>
          </div>
          {loadingForecast ? (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="w-4 h-4 text-petroleo-500 animate-spin" />
              <span className="text-xs text-slate-500 ml-2">Calculando...</span>
            </div>
          ) : forecast.length === 0 ? (
            <p className="text-xs text-slate-500">No se pudo calcular la estimacion</p>
          ) : (
            <div className="space-y-2">
              {forecast.map((f) => {
                const probColors = {
                  alta: { bg: 'bg-red-900/20', text: 'text-red-400', border: 'border-red-800/50' },
                  media: { bg: 'bg-yellow-900/20', text: 'text-yellow-400', border: 'border-yellow-800/50' },
                  baja: { bg: 'bg-emerald-900/20', text: 'text-emerald-400', border: 'border-emerald-800/50' },
                };
                const dirColors2 = {
                  SUBE: 'text-red-400',
                  BAJA: 'text-emerald-400',
                  IGUAL: 'text-slate-400',
                };
                const prob = f.direction === 'SUBE' ? probColors[f.probability] : f.direction === 'BAJA' ? probColors.baja : probColors.media;
                const isExpanded = expandedFuel === f.fuel;
                const d = f.detail;

                return (
                  <div key={f.fuel}>
                    <button
                      onClick={() => setExpandedFuel(isExpanded ? null : f.fuel)}
                      className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${prob.bg} ${prob.border} hover:brightness-110 cursor-pointer`}
                    >
                      <div className="flex items-center gap-2">
                        {f.direction === 'SUBE' ? (
                          <TrendingUp className={`w-4 h-4 ${dirColors2[f.direction]}`} />
                        ) : f.direction === 'BAJA' ? (
                          <TrendingDown className={`w-4 h-4 ${dirColors2[f.direction]}`} />
                        ) : (
                          <Minus className="w-4 h-4 text-slate-400" />
                        )}
                        <div className="text-left">
                          <span className="text-sm font-medium text-white">{f.label}</span>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-slate-500">${f.current.toFixed(2)}</span>
                            <span className="text-xs text-slate-600">→</span>
                            <span className={`text-xs font-medium ${dirColors2[f.direction]}`}>
                              ${f.estimated.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right">
                          <span className={`text-sm font-semibold ${dirColors2[f.direction]}`}>
                            {f.direction === 'SUBE' ? '+' : ''}{f.change_pct.toFixed(2)}%
                          </span>
                          <div className="flex items-center gap-1 mt-0.5 justify-end">
                            <span className="text-xs text-slate-500">Prob:</span>
                            <span className={`text-xs font-medium ${prob.text}`}>
                              {f.probability.charAt(0).toUpperCase() + f.probability.slice(1)}
                            </span>
                          </div>
                        </div>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-slate-500" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-500" />
                        )}
                      </div>
                    </button>

                    {isExpanded && d && (
                      <div className="mt-1 rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-4 animate-in">
                        <div className={`rounded-lg p-3 ${prob.bg} border ${prob.border}`}>
                          <h5 className={`text-sm font-semibold ${dirColors2[f.direction]} mb-2`}>
                            ¿Por que {f.direction === 'BAJA' ? 'baja' : f.direction === 'SUBE' ? 'sube' : 'se mantiene'}?
                          </h5>
                          <p className="text-xs text-slate-300 leading-relaxed">
                            {f.direction === 'SUBE' ? (
                              <>
                                El WTI promedio predicho es <strong className="text-white">${d.wti_predicted.toFixed(2)}/barril</strong>
                                {d.wti_change_pct > 0 ? `, un aumento del ${d.wti_change_pct.toFixed(1)}%.` : '.'}{' '}
                                Esto eleva la formula del gobierno a <strong className="text-white">${d.theoretical_price.toFixed(3)}/galon</strong>.
                                {d.band_status === 'TECHO' ? ` La banda limita la subida a +5%, resultando en $${f.estimated.toFixed(3)}.` : ` El precio queda dentro de la banda permitida.`}
                              </>
                            ) : f.direction === 'BAJA' ? (
                              <>
                                El WTI predicho de <strong className="text-white">${d.wti_predicted.toFixed(2)}/barril</strong> genera un precio teorico de <strong className="text-white">${d.theoretical_price.toFixed(3)}/galon</strong>, menor al actual. La banda limita la bajada al -10%, resultando en ${f.estimated.toFixed(3)}.
                              </>
                            ) : (
                              <>El WTI se mantiene estable y la formula no genera un cambio significativo.</>
                            )}
                          </p>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
                            <h5 className="text-xs text-blue-400 font-semibold uppercase tracking-wider">Precio del Petroleo (WTI)</h5>
                          </div>
                          <div className="grid grid-cols-3 gap-2">
                            <div className="bg-slate-900/50 rounded p-2">
                              <span className="text-xs text-slate-500 block">Actual</span>
                              <span className="text-sm font-semibold text-white">${d.wti_current.toFixed(2)}</span>
                            </div>
                            <div className="bg-slate-900/50 rounded p-2">
                              <span className="text-xs text-slate-500 block">Predicho (avg 1-10)</span>
                              <span className={`text-sm font-semibold ${d.wti_change_pct > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                ${d.wti_predicted.toFixed(2)}
                              </span>
                            </div>
                            <div className="bg-slate-900/50 rounded p-2">
                              <span className="text-xs text-slate-500 block">Rango IC 95%</span>
                              <span className="text-xs font-medium text-slate-300">
                                ${d.wti_confidence.lower.toFixed(1)} - ${d.wti_confidence.upper.toFixed(1)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Shield className="w-3.5 h-3.5 text-petroleo-400" />
                            <h5 className="text-xs text-petroleo-400 font-semibold uppercase tracking-wider">Sistema de Bandas</h5>
                          </div>
                          <div className="bg-slate-900/50 rounded p-2">
                            <div className="grid grid-cols-3 gap-2">
                              <div className="text-center">
                                <span className="text-xs text-emerald-500 block">Piso (-10%)</span>
                                <span className="text-xs font-semibold text-slate-300">${d.min_price.toFixed(3)}</span>
                              </div>
                              <div className="text-center">
                                <span className={`text-xs block ${d.band_status === 'TECHO' ? 'text-red-400' : d.band_status === 'PISO' ? 'text-emerald-400' : 'text-yellow-400'}`}>
                                  {d.band_status === 'TECHO' ? 'Tope ↑' : d.band_status === 'PISO' ? 'Tope ↓' : 'Dentro'}
                                </span>
                                <span className="text-sm font-bold text-white">${f.estimated.toFixed(3)}</span>
                              </div>
                              <div className="text-center">
                                <span className="text-xs text-red-500 block">Techo (+5%)</span>
                                <span className="text-xs font-semibold text-slate-300">${d.max_price.toFixed(3)}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {isExpanded && !d && (
                      <div className="mt-1 rounded-lg border border-slate-700/50 bg-slate-800/40 p-4">
                        <p className="text-xs text-slate-500">Detalle no disponible.</p>
                      </div>
                    )}
                  </div>
                );
              })}
              <p className="text-xs text-slate-600 italic mt-1">* Haz clic en un combustible para ver el detalle.</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-petroleo-700/30 flex items-center justify-center">
            <Clock className="w-5 h-5 text-petroleo-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">
              Proximo ajuste de precios
            </h3>
            <p className="text-xs text-slate-500">
              <CalendarDays className="w-3 h-3 inline mr-1" />
              {format(nextUpdate, "EEEE d 'de' MMMM, yyyy", { locale: es })}
            </p>
          </div>
        </div>

        <div className="text-right">
          <span className="text-2xl font-bold text-white">{daysRemaining}</span>
          <span className="text-sm text-slate-400 ml-1">
            {daysRemaining === 1 ? 'dia' : 'dias'}
          </span>
          {daysRemaining <= 5 && (
            <p className="text-xs text-slate-500">
              {hoursRemaining}h {minutesRemaining}m
            </p>
          )}
        </div>
      </div>

      {/* Barra de progreso */}
      <div className="w-full">
        <div className="flex justify-between text-xs text-slate-500 mb-1">
          <span>Ultimo ajuste</span>
          <span>Proximo ajuste</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-petroleo-700 to-petroleo-500 rounded-full transition-all duration-1000"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-xs text-slate-500 text-center mt-1">
          {daysRemaining <= 3
            ? 'El ajuste de precios esta muy cerca'
            : daysRemaining <= 7
            ? 'Falta menos de una semana'
            : `Faltan ${daysRemaining} dias para el proximo ajuste`}
        </p>
      </div>

      {/* Mini prediccion */}
      <div className="mt-4 pt-4 border-t border-slate-700/50">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs text-slate-500 uppercase tracking-wider font-medium">
            Estimacion para el {format(nextUpdate, "d 'de' MMMM", { locale: es })}
          </h4>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
            Recalcular
          </button>
        </div>
        {loadingForecast ? (
          <div className="flex items-center justify-center py-3">
            <Loader2 className="w-4 h-4 text-petroleo-500 animate-spin" />
            <span className="text-xs text-slate-500 ml-2">Calculando...</span>
          </div>
        ) : forecast.length === 0 ? (
          <p className="text-xs text-slate-500">No se pudo calcular la estimacion</p>
        ) : (
          <div className="space-y-2">
            {forecast.map((f) => {
              const probColors = {
                alta: { bg: 'bg-red-900/20', text: 'text-red-400', border: 'border-red-800/50' },
                media: { bg: 'bg-yellow-900/20', text: 'text-yellow-400', border: 'border-yellow-800/50' },
                baja: { bg: 'bg-emerald-900/20', text: 'text-emerald-400', border: 'border-emerald-800/50' },
              };
              const dirColors = {
                SUBE: 'text-red-400',
                BAJA: 'text-emerald-400',
                IGUAL: 'text-slate-400',
              };
              const prob = f.direction === 'SUBE' ? probColors[f.probability] : f.direction === 'BAJA' ? probColors.baja : probColors.media;
              const isExpanded = expandedFuel === f.fuel;
              const d = f.detail;

              return (
                <div key={f.fuel}>
                  {/* Tarjeta clickeable */}
                  <button
                    onClick={() => setExpandedFuel(isExpanded ? null : f.fuel)}
                    className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${prob.bg} ${prob.border} hover:brightness-110 cursor-pointer`}
                  >
                    <div className="flex items-center gap-2">
                      {f.direction === 'SUBE' ? (
                        <TrendingUp className={`w-4 h-4 ${dirColors[f.direction]}`} />
                      ) : f.direction === 'BAJA' ? (
                        <TrendingDown className={`w-4 h-4 ${dirColors[f.direction]}`} />
                      ) : (
                        <Minus className="w-4 h-4 text-slate-400" />
                      )}
                      <div className="text-left">
                        <span className="text-sm font-medium text-white">{f.label}</span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-slate-500">${f.current.toFixed(2)}</span>
                          <span className="text-xs text-slate-600">→</span>
                          <span className={`text-xs font-medium ${dirColors[f.direction]}`}>
                            ${f.estimated.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-right">
                        <span className={`text-sm font-semibold ${dirColors[f.direction]}`}>
                          {f.direction === 'SUBE' ? '+' : ''}{f.change_pct.toFixed(2)}%
                        </span>
                        <div className="flex items-center gap-1 mt-0.5 justify-end">
                          <span className="text-xs text-slate-500">Prob:</span>
                          <span className={`text-xs font-medium ${prob.text}`}>
                            {f.probability.charAt(0).toUpperCase() + f.probability.slice(1)}
                          </span>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-slate-500" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-slate-500" />
                      )}
                    </div>
                  </button>

                  {/* Panel de detalle expandido */}
                  {isExpanded && d && (
                    <div className="mt-1 rounded-lg border border-slate-700/50 bg-slate-800/40 p-4 space-y-4 animate-in">

                      {/* Resumen: Por qué sube/baja */}
                      <div className={`rounded-lg p-3 ${prob.bg} border ${prob.border}`}>
                        <h5 className={`text-sm font-semibold ${dirColors[f.direction]} mb-2`}>
                          ¿Por que {f.direction === 'BAJA' ? 'baja' : f.direction === 'SUBE' ? 'sube' : 'se mantiene'}?
                        </h5>
                        <p className="text-xs text-slate-300 leading-relaxed">
                          {f.direction === 'BAJA' ? (
                            <>
                              El modelo predice que el WTI promedio para los dias 1-10 de abril sera{' '}
                              <strong className="text-white">${d.wti_predicted.toFixed(2)}/barril</strong>
                              {d.wti_change_pct < 0
                                ? `, una caida del ${Math.abs(d.wti_change_pct).toFixed(1)}% vs el precio actual ($${d.wti_current.toFixed(2)}).`
                                : d.wti_change_pct > 0
                                ? `, un aumento del ${d.wti_change_pct.toFixed(1)}%, pero la formula del gobierno calcula un precio teorico ($${d.theoretical_price.toFixed(3)}) menor al actual ($${f.current.toFixed(3)}).`
                                : '.'
                              }{' '}
                              Con este WTI, la formula del Decreto 308 calcula un precio de{' '}
                              <strong className="text-white">${d.theoretical_price.toFixed(3)}/galon</strong>,
                              que es{' '}
                              {d.theoretical_price < f.current
                                ? `menor al precio actual. La banda de precios limita la bajada al -10%, resultando en $${f.estimated.toFixed(3)}.`
                                : `mayor al actual, pero dentro de la banda permitida.`
                              }
                            </>
                          ) : f.direction === 'SUBE' ? (
                            <>
                              El WTI promedio predicho es <strong className="text-white">${d.wti_predicted.toFixed(2)}/barril</strong>
                              {d.wti_change_pct > 0
                                ? `, un aumento del ${d.wti_change_pct.toFixed(1)}%.`
                                : '.'
                              }{' '}
                              Esto eleva la formula del gobierno a{' '}
                              <strong className="text-white">${d.theoretical_price.toFixed(3)}/galon</strong>.
                              {d.band_status === 'TECHO'
                                ? ` La banda limita la subida a +5%, resultando en $${f.estimated.toFixed(3)}.`
                                : ` El precio queda dentro de la banda permitida.`
                              }
                            </>
                          ) : (
                            <>El WTI se mantiene estable y la formula no genera un cambio significativo.</>
                          )}
                        </p>
                      </div>

                      {/* Paso 1: WTI */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
                          <h5 className="text-xs text-blue-400 font-semibold uppercase tracking-wider">
                            Paso 1: Precio del Petroleo (<Sigla term="WTI" />)
                          </h5>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div className="bg-slate-900/50 rounded p-2">
                            <span className="text-xs text-slate-500 block">Actual</span>
                            <span className="text-sm font-semibold text-white">${d.wti_current.toFixed(2)}</span>
                          </div>
                          <div className="bg-slate-900/50 rounded p-2">
                            <span className="text-xs text-slate-500 block">Predicho (<Sigla term="avg">avg</Sigla> 1-10)</span>
                            <span className={`text-sm font-semibold ${d.wti_change_pct > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                              ${d.wti_predicted.toFixed(2)}
                            </span>
                          </div>
                          <div className="bg-slate-900/50 rounded p-2">
                            <span className="text-xs text-slate-500 block">Rango <Sigla term="IC" /> 95%</span>
                            <span className="text-xs font-medium text-slate-300">
                              ${d.wti_confidence.lower.toFixed(1)} - ${d.wti_confidence.upper.toFixed(1)}
                            </span>
                          </div>
                        </div>
                        {d.wti_data_points > 0 && (
                          <p className="text-xs text-slate-600 mt-1">
                            Basado en {d.wti_data_points.toLocaleString()} dias de datos historicos
                            {d.wti_weights && Object.keys(d.wti_weights).length > 0 && (
                              <> | Pesos: {Object.entries(d.wti_weights).map(([m, w], i) => (
                                <span key={m}>
                                  {i > 0 && ', '}
                                  <Sigla term={m.toUpperCase()}>
                                    {m.toUpperCase()}
                                  </Sigla>{' '}{(Number(w) * 100).toFixed(0)}%
                                </span>
                              ))}</>
                            )}
                          </p>
                        )}
                      </div>

                      {/* Paso 2: Formula */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Calculator className="w-3.5 h-3.5 text-amber-400" />
                          <h5 className="text-xs text-amber-400 font-semibold uppercase tracking-wider">
                            Paso 2: Formula Decreto 308
                          </h5>
                        </div>
                        <div className="bg-slate-900/50 rounded p-2 space-y-1">
                          {d.formula_breakdown && Object.keys(d.formula_breakdown).length > 0 ? (
                            <>
                              {[
                                { key: 'import_cost_gallon', label: 'Costo importacion' , sigla: 'CIF' },
                                { key: 'transport_cost', label: 'Transporte' },
                                { key: 'storage_cost', label: 'Almacenamiento' },
                                { key: 'petroecuador_margin', label: 'Margen Petroecuador' },
                                { key: 'capital_cost', label: 'Costo de capital' },
                                { key: 'iva_amount', label: 'IVA (15%)' },
                                { key: 'commercial_margin', label: 'Margen comercializacion' },
                              ].map((item) => {
                                const val = d.formula_breakdown[item.key];
                                if (val === undefined) return null;
                                return (
                                  <div key={item.key} className="flex justify-between text-xs">
                                    <span className="text-slate-500">
                                      {item.label}
                                      {'sigla' in item && (item as any).sigla && (
                                        <> (<Sigla term={(item as any).sigla} />)</>
                                      )}
                                    </span>
                                    <span className="text-slate-300">${Number(val).toFixed(3)}</span>
                                  </div>
                                );
                              })}
                              <div className="flex justify-between text-xs font-semibold border-t border-slate-700 pt-1 mt-1">
                                <span className="text-slate-400">Precio teorico</span>
                                <span className="text-white">${d.theoretical_price.toFixed(3)}</span>
                              </div>
                            </>
                          ) : (
                            <div className="flex justify-between text-xs">
                              <span className="text-slate-500">Precio teorico calculado</span>
                              <span className="text-white">${d.theoretical_price.toFixed(3)}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Paso 3: Banda */}
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Shield className="w-3.5 h-3.5 text-petroleo-400" />
                          <h5 className="text-xs text-petroleo-400 font-semibold uppercase tracking-wider">
                            Paso 3: Sistema de Bandas
                          </h5>
                        </div>
                        <div className="bg-slate-900/50 rounded p-2">
                          <div className="grid grid-cols-3 gap-2 mb-2">
                            <div className="text-center">
                              <span className="text-xs text-emerald-500 block">Piso (-10%)</span>
                              <span className="text-xs font-semibold text-slate-300">${d.min_price.toFixed(3)}</span>
                            </div>
                            <div className="text-center">
                              <span className={`text-xs block ${
                                d.band_status === 'TECHO' ? 'text-red-400'
                                : d.band_status === 'PISO' ? 'text-emerald-400'
                                : 'text-yellow-400'
                              }`}>
                                {d.band_status === 'TECHO' ? 'Tope alcanzado ↑'
                                  : d.band_status === 'PISO' ? 'Tope alcanzado ↓'
                                  : 'Dentro de banda'}
                              </span>
                              <span className="text-sm font-bold text-white">${f.estimated.toFixed(3)}</span>
                            </div>
                            <div className="text-center">
                              <span className="text-xs text-red-500 block">Techo (+5%)</span>
                              <span className="text-xs font-semibold text-slate-300">${d.max_price.toFixed(3)}</span>
                            </div>
                          </div>
                          {/* Visual band bar */}
                          <div className="relative h-3 bg-slate-700 rounded-full overflow-hidden">
                            <div className="absolute inset-0 flex">
                              <div className="bg-emerald-800/40" style={{ width: '10%' }} />
                              <div className="bg-slate-600/30 flex-1" />
                              <div className="bg-red-800/40" style={{ width: '5%' }} />
                            </div>
                            {/* Marker for result */}
                            <div
                              className="absolute top-0 bottom-0 w-1 bg-white rounded-full"
                              style={{
                                left: `${Math.max(0, Math.min(100,
                                  ((f.estimated - d.min_price) / (d.max_price - d.min_price)) * 100
                                ))}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Si no hay detalle pero está expandido */}
                  {isExpanded && !d && (
                    <div className="mt-1 rounded-lg border border-slate-700/50 bg-slate-800/40 p-4">
                      <p className="text-xs text-slate-500">
                        Detalle no disponible. Esta estimacion se baso en el modelo ensemble directo.
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
            <p className="text-xs text-slate-600 italic mt-1">
              * Haz clic en un combustible para ver el detalle del calculo.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
