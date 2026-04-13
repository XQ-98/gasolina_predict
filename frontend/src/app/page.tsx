'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  Brain,
  Layers,
  Newspaper,
  History,
  Loader2,
  RefreshCw,
  Sun,
  Moon,
  Fuel,
  ChevronDown,
} from 'lucide-react';
import FuelPriceCards from '@/components/FuelPriceCards';
import NextUpdateCountdown from '@/components/NextUpdateCountdown';
import WtiTracker from '@/components/WtiTracker';
import HistoricalChart from '@/components/HistoricalChart';
import PredictionChart from '@/components/PredictionChart';
import PredictionSummary from '@/components/PredictionSummary';
import BandSimulator from '@/components/BandSimulator';
import BandHistory from '@/components/BandHistory';
import AnalysisPanel from '@/components/AnalysisPanel';
import ModelMetrics from '@/components/ModelMetrics';
import ModelComparison from '@/components/ModelComparison';
import NewsPanel from '@/components/NewsPanel';
import PredictionHistory from '@/components/PredictionHistory';
import {
  fetchCurrentPrices,
  fetchHistoricalPrices,
  fetchPrediction,
  fetchAnalysis,
  fetchNews,
} from '@/lib/api';

type Tab = 'dashboard' | 'prediction' | 'bands' | 'history' | 'news';

const fuelTypes = [
  { value: 'extra', label: 'Extra' },
  { value: 'ecopais', label: 'EcoPais' },
  { value: 'super_95', label: 'Super 95' },
  { value: 'diesel', label: 'Diesel' },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  // Data state
  const [currentPrices, setCurrentPrices] = useState<FuelPrice[] | null>(null);
  const [historical, setHistorical] = useState<HistoricalPrice[] | null>(null);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [news, setNews] = useState<NewsArticle[] | null>(null);

  // Settings
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [selectedFuel, setSelectedFuel] = useState('extra');
  const [historyYears, setHistoryYears] = useState(5);
  const [horizonMonths, setHorizonMonths] = useState(6);

  const setLoadingKey = (key: string, value: boolean) => {
    setLoading((prev) => ({ ...prev, [key]: value }));
  };

  // Theme toggle
  useEffect(() => {
    if (theme === 'light') {
      document.body.classList.add('light');
    } else {
      document.body.classList.remove('light');
    }
  }, [theme]);

  // Load current prices
  const loadCurrentPrices = useCallback(async () => {
    setLoadingKey('prices', true);
    try {
      const data = await fetchCurrentPrices();
      setCurrentPrices(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingKey('prices', false);
    }
  }, []);

  // Load historical
  const loadHistorical = useCallback(async () => {
    setLoadingKey('historical', true);
    try {
      const data = await fetchHistoricalPrices(historyYears);
      setHistorical(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingKey('historical', false);
    }
  }, [historyYears]);

  // Load prediction
  const loadPrediction = async () => {
    setLoadingKey('prediction', true);
    setError(null);
    try {
      const data = await fetchPrediction(selectedFuel, horizonMonths);
      setPrediction(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingKey('prediction', false);
    }
  };

  // Load analysis
  const loadAnalysis = useCallback(async () => {
    setLoadingKey('analysis', true);
    try {
      const data = await fetchAnalysis();
      setAnalysis(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingKey('analysis', false);
    }
  }, []);

  // Load news
  const loadNews = useCallback(async () => {
    setLoadingKey('news', true);
    try {
      const data = await fetchNews();
      setNews(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingKey('news', false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadCurrentPrices();
    loadHistorical();
  }, [loadCurrentPrices, loadHistorical]);

  const tabs = [
    { id: 'dashboard' as Tab, label: 'Dashboard', icon: BarChart3 },
    { id: 'prediction' as Tab, label: 'Prediccion', icon: Brain },
    { id: 'bands' as Tab, label: 'Sistema de Bandas', icon: Layers },
    { id: 'history' as Tab, label: 'Historial', icon: History },
    { id: 'news' as Tab, label: 'Noticias', icon: Newspaper },
  ];

  const currentFuelPrice =
    currentPrices?.find((p) => p.type === selectedFuel)?.price_per_gallon || 0;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-petroleo-700 rounded-lg flex items-center justify-center">
                <Fuel className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">GasPredict Ecuador</h1>
                <p className="text-xs text-slate-400">
                  Prediccion Inteligente de Precios de Combustibles
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {/* Fuel selector */}
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-500">Combustible:</span>
                <select
                  value={selectedFuel}
                  onChange={(e) => setSelectedFuel(e.target.value)}
                  className="select-custom text-xs py-1"
                >
                  {fuelTypes.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Theme toggle */}
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 transition-colors"
                title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
              >
                {theme === 'dark' ? (
                  <Sun className="w-4 h-4 text-yellow-400" />
                ) : (
                  <Moon className="w-4 h-4 text-slate-400" />
                )}
              </button>
            </div>
          </div>

          {/* Tabs */}
          <nav className="flex gap-1 mt-4 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id === 'news' && !news) loadNews();
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'bg-petroleo-700 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {error && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-4 mb-6">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-500 text-xs mt-1 underline"
            >
              Cerrar
            </button>
          </div>
        )}

        {/* ===== DASHBOARD ===== */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Countdown */}
            <NextUpdateCountdown />

            {/* Price Cards */}
            {loading.prices ? (
              <div className="card flex items-center justify-center h-32">
                <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
              </div>
            ) : currentPrices ? (
              <FuelPriceCards prices={currentPrices} />
            ) : null}

            {/* WTI Tracker */}
            <WtiTracker />

            {/* Historical Chart */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="card-header mb-0">Precios Historicos de Combustibles</h2>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-slate-500">Periodo:</span>
                    {[
                      { value: 1, label: '1A' },
                      { value: 2, label: '2A' },
                      { value: 3, label: '3A' },
                      { value: 5, label: '5A' },
                    ].map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setHistoryYears(opt.value)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                          historyYears === opt.value
                            ? 'bg-petroleo-700 text-white'
                            : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={loadHistorical}
                    className="btn-secondary text-xs py-1 px-2"
                  >
                    <RefreshCw className="w-3 h-3" />
                  </button>
                </div>
              </div>
              {loading.historical ? (
                <div className="flex items-center justify-center h-96">
                  <Loader2 className="w-8 h-8 text-petroleo-500 animate-spin" />
                </div>
              ) : historical && historical.length > 0 ? (
                <HistoricalChart data={historical} />
              ) : (
                <div className="text-center text-slate-500 py-16">
                  No hay datos historicos disponibles
                </div>
              )}
            </div>

            {/* Quick News */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="card-header mb-0">Ultimas Noticias</h2>
                <button
                  onClick={loadNews}
                  disabled={loading.news}
                  className="btn-secondary text-xs flex items-center gap-1"
                >
                  {loading.news ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Newspaper className="w-3 h-3" />
                  )}
                  {news ? 'Actualizar' : 'Cargar'}
                </button>
              </div>
              {loading.news ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
                </div>
              ) : news && news.length > 0 ? (
                <div className="space-y-2">
                  {news.slice(0, 3).map((article, i) => (
                    <div
                      key={i}
                      className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-3 hover:bg-slate-800/60 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            article.sentiment === 'positivo'
                              ? 'bg-emerald-900/30 text-emerald-400'
                              : article.sentiment === 'negativo'
                              ? 'bg-red-900/30 text-red-400'
                              : 'bg-slate-800/50 text-slate-400'
                          }`}
                        >
                          {article.sentiment}
                        </span>
                        <span className="text-xs text-slate-600">{article.date}</span>
                      </div>
                      <h4 className="text-sm font-medium text-white">{article.title}</h4>
                    </div>
                  ))}
                  <button
                    onClick={() => setActiveTab('news')}
                    className="w-full text-center text-sm text-petroleo-400 hover:text-petroleo-300 py-2"
                  >
                    Ver todas las noticias
                  </button>
                </div>
              ) : (
                <div className="text-center text-slate-500 py-8">
                  <Newspaper className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                  <p className="text-sm">Haz clic en &quot;Cargar&quot; para ver noticias</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===== PREDICCION ===== */}
        {activeTab === 'prediction' && (
          <div className="space-y-6">
            {/* Controles */}
            <div className="card">
              <h2 className="card-header">Configuracion de Prediccion</h2>
              <div className="flex flex-wrap gap-4 items-end">
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Combustible</label>
                  <select
                    value={selectedFuel}
                    onChange={(e) => setSelectedFuel(e.target.value)}
                    className="select-custom"
                  >
                    {fuelTypes.map((f) => (
                      <option key={f.value} value={f.value}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Horizonte</label>
                  <select
                    value={horizonMonths}
                    onChange={(e) => setHorizonMonths(parseInt(e.target.value))}
                    className="select-custom"
                  >
                    <option value={1}>1 mes</option>
                    <option value={3}>3 meses</option>
                    <option value={6}>6 meses</option>
                    <option value={9}>9 meses</option>
                    <option value={12}>12 meses</option>
                  </select>
                </div>
                <button
                  onClick={loadPrediction}
                  disabled={loading.prediction}
                  className="btn-primary flex items-center gap-2"
                >
                  {loading.prediction ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Entrenando modelos...
                    </>
                  ) : (
                    <>
                      <Brain className="w-4 h-4" />
                      Generar Prediccion
                    </>
                  )}
                </button>
              </div>
              {loading.prediction && (
                <p className="text-xs text-slate-500 mt-3">
                  Esto puede tardar unos minutos. Se estan entrenando 3 modelos (SARIMA,
                  XGBoost, LSTM)...
                </p>
              )}
            </div>

            {/* Resultados */}
            {prediction && (
              <>
                {/* Resumen */}
                <PredictionSummary
                  prediction={prediction}
                  currentPrice={currentFuelPrice}
                />

                {/* Grafico de prediccion */}
                <div className="card">
                  <h2 className="card-header">Prediccion del Precio</h2>
                  {historical && historical.length > 0 ? (
                    <PredictionChart
                      prediction={prediction}
                      historicalData={historical}
                      fuelType={selectedFuel}
                    />
                  ) : (
                    <p className="text-slate-500 text-sm">
                      Carga datos historicos primero para ver el grafico completo
                    </p>
                  )}
                </div>

                {/* Comparacion de modelos */}
                <div className="card">
                  <h2 className="card-header">Comparacion de Modelos</h2>
                  <p className="text-xs text-slate-500 mb-4">
                    Comparacion interactiva entre SARIMA, XGBoost y LSTM. Activa o desactiva
                    cada modelo para ver su prediccion individual.
                  </p>
                  {historical && historical.length > 0 ? (
                    <ModelComparison
                      prediction={prediction}
                      historicalData={historical}
                      fuelType={selectedFuel}
                    />
                  ) : (
                    <p className="text-slate-500 text-sm">
                      Carga datos historicos primero
                    </p>
                  )}
                </div>

                {/* Metricas */}
                {prediction.metrics && prediction.models?.weights && (
                  <div className="card">
                    <h2 className="card-header">Metricas de los Modelos</h2>
                    <ModelMetrics
                      metrics={prediction.metrics}
                      weights={prediction.models.weights}
                    />
                  </div>
                )}

                {/* Analisis */}
                <div className="card">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="card-header mb-0">Analisis de Factores</h2>
                    <button
                      onClick={loadAnalysis}
                      disabled={loading.analysis}
                      className="btn-secondary text-xs flex items-center gap-1"
                    >
                      {loading.analysis ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3 h-3" />
                      )}
                      {analysis ? 'Actualizar' : 'Cargar'}
                    </button>
                  </div>
                  {loading.analysis ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 text-petroleo-500 animate-spin" />
                    </div>
                  ) : analysis ? (
                    <AnalysisPanel analysis={analysis} />
                  ) : (
                    <div className="text-center text-slate-500 py-8">
                      Haz clic en &quot;Cargar&quot; para ver el analisis de factores
                    </div>
                  )}
                </div>
              </>
            )}

            {!prediction && !loading.prediction && (
              <div className="card text-center py-16">
                <Brain className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                <p className="text-slate-500 mb-2">
                  Selecciona un combustible y horizonte de prediccion
                </p>
                <p className="text-xs text-slate-600">
                  Los modelos SARIMA, XGBoost y LSTM seran entrenados con datos historicos
                  para generar predicciones mensuales con intervalos de confianza.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ===== SISTEMA DE BANDAS ===== */}
        {activeTab === 'bands' && (
          <div className="space-y-6">
            <BandSimulator />
            <BandHistory />
          </div>
        )}

        {/* ===== HISTORIAL DE PREDICCIONES ===== */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            <div className="card">
              <h2 className="card-header">
                Historial de Predicciones
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Registro de todas las predicciones realizadas por el sistema. Cuando se
                conocen los precios reales (dia 11), se calcula la precision automaticamente.
                Un acierto significa que el error fue menor al 2%.
              </p>
            </div>
            <PredictionHistory />
          </div>
        )}

        {/* ===== NOTICIAS ===== */}
        {activeTab === 'news' && (
          <div className="space-y-6">
            <div className="card">
              <h2 className="card-header">
                Noticias de Combustibles en Ecuador
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Noticias recientes sobre combustibles en Ecuador con analisis automatico de
                sentimiento. El sentimiento puede influir en las decisiones de ajuste de
                precios.
              </p>
              {loading.news ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-8 h-8 text-petroleo-500 animate-spin" />
                </div>
              ) : news && news.length > 0 ? (
                <NewsPanel
                  articles={news}
                  onRefresh={loadNews}
                  loading={loading.news || false}
                />
              ) : (
                <div className="text-center py-16">
                  <Newspaper className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                  <p className="text-slate-500 mb-4">
                    Carga las noticias mas recientes sobre combustibles
                  </p>
                  <button
                    onClick={loadNews}
                    disabled={loading.news}
                    className="btn-primary flex items-center gap-2 mx-auto"
                  >
                    {loading.news ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Newspaper className="w-4 h-4" />
                    )}
                    Cargar Noticias
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-600">
          GasPredict Ecuador - Prediccion inteligente de precios de combustibles.
          Los precios se actualizan el dia 11 de cada mes. Este sistema es solo informativo
          y no constituye asesoramiento financiero.
        </div>
      </footer>
    </div>
  );
}
