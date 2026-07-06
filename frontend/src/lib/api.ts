const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchAppInfo(): Promise<{ version: string; app: string }> {
  try {
    const res = await fetch(`${API_BASE}/`);
    if (!res.ok) return { version: '1.1.0', app: 'GasPredict Ecuador' };
    const data = await res.json();
    return { version: data.version || '1.1.0', app: data.app || 'GasPredict Ecuador' };
  } catch {
    return { version: '1.1.0', app: 'GasPredict Ecuador' };
  }
}

export async function fetchCurrentPrices(): Promise<FuelPrice[]> {
  const res = await fetch(`${API_BASE}/api/prices/current`);
  if (!res.ok) throw new Error('Error al obtener precios actuales');
  const data = await res.json();
  // El backend devuelve { date, prices: [...], next_update: {...} }
  const prices = data.prices || data;
  return prices.map((p: Record<string, unknown>) => ({
    type: p.fuel_type || p.type,
    name: p.name,
    price_per_gallon: p.price ?? p.price_per_gallon,
    previous_price: p.previous_price,
    change_percent: p.change_pct ?? p.change_percent,
    change_direction: (p.change_pct ?? p.change_percent ?? 0) as number > 0 ? 'SUBE' : (p.change_pct ?? p.change_percent ?? 0) as number < 0 ? 'BAJA' : 'IGUAL',
    effective_date: data.date ? (() => { const d = new Date(data.date + 'T00:00:00'); d.setDate(d.getDate() + 1); return d.toISOString().split('T')[0]; })() : '',
    band_applied: p.band_status || p.band_applied || 'DENTRO',
  }));
}

export async function fetchHistoricalPrices(years: number = 5): Promise<HistoricalPrice[]> {
  const res = await fetch(`${API_BASE}/api/prices/historical?years=${years}`);
  if (!res.ok) throw new Error('Error al obtener precios historicos');
  const data = await res.json();
  return data.data || data;
}

export async function fetchWtiPrice(): Promise<WtiData> {
  const res = await fetch(`${API_BASE}/api/wti`);
  if (!res.ok) throw new Error('Error al obtener precio WTI');
  const data = await res.json();
  // Backend devuelve { current_price, changes: { change_24h, ... }, historical: [...] }
  return {
    current: data.current_price ?? data.current,
    change_24h: data.changes?.change_24h_pct ?? data.change_24h ?? 0,
    change_7d: data.changes?.change_7d_pct ?? data.change_7d ?? 0,
    change_30d: data.changes?.change_30d_pct ?? data.change_30d ?? 0,
    historical: data.historical || [],
  };
}

export async function fetchPrediction(fuelType: string, months: number = 6): Promise<PredictionResult> {
  const res = await fetch(`${API_BASE}/api/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fuel_type: fuelType, months, approach: 'two_layer' }),
  });
  if (!res.ok) throw new Error('Error al generar prediccion');
  const d = await res.json();

  // Normalizar predictions: backend usa {date, price}, frontend espera {month, predicted_price, ...}
  const preds = (d.predictions || []).map((p: Record<string, unknown>, i: number) => ({
    month: p.date || p.month,
    predicted_price: p.price ?? p.predicted_price,
    lower_bound: d.confidence_interval?.lower?.[i] ?? (p as any).lower_bound ?? 0,
    upper_bound: d.confidence_interval?.upper?.[i] ?? (p as any).upper_bound ?? 0,
    band_status: p.band_status || 'DENTRO',
    change_from_current: d.current_price
      ? ((p.price ?? p.predicted_price) as number) - d.current_price
      : 0,
  }));

  // Normalizar dates para models
  const dates = preds.map((p: { month: string }) => p.month);

  // Normalizar models
  const indiv = d.individual_predictions || {};
  const models: ModelPredictions = {
    sarima: indiv.sarima || [],
    xgboost: indiv.xgboost || [],
    lstm: indiv.lstm || [],
    ensemble: d.ensemble_prices || preds.map((p: { predicted_price: number }) => p.predicted_price),
    dates,
    weights: d.weights || {},
  };

  // Normalizar confidence_intervals como array de objetos
  const ciArr: ConfidenceInterval[] = dates.map((date: string, i: number) => ({
    date,
    lower: d.confidence_interval?.lower?.[i] ?? 0,
    upper: d.confidence_interval?.upper?.[i] ?? 0,
    predicted: preds[i]?.predicted_price ?? 0,
  }));

  return {
    fuel_type: d.fuel_type || fuelType,
    predictions: preds,
    models,
    metrics: d.metrics || {},
    confidence_intervals: ciArr,
    approach: d.approach || 'ensemble',
    layer_1_wti: d.layer_1_wti,
    layer_2_formula: d.layer_2_formula,
  };
}

export async function fetchAnalysis(): Promise<AnalysisData> {
  const res = await fetch(`${API_BASE}/api/analysis`);
  if (!res.ok) throw new Error('Error al obtener analisis');
  return res.json();
}

export async function fetchBandSimulation(wtiPrice: number, fuelType: string = 'extra'): Promise<BandSimulation> {
  const res = await fetch(`${API_BASE}/api/band/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ wti_price: wtiPrice, fuel_type: fuelType }),
  });
  if (!res.ok) throw new Error('Error al simular banda');
  const d = await res.json();
  return {
    current_price: d.current_price ?? 0,
    theoretical_price: d.theoretical_price ?? 0,
    band_result: d.final_price ?? d.band_result ?? 0,
    band_status: d.band_status || 'DENTRO',
    max_possible: d.max_price ?? d.max_possible ?? 0,
    min_possible: d.min_price ?? d.min_possible ?? 0,
    wti_price: d.wti_input ?? d.wti_price ?? wtiPrice,
    formula_breakdown: d.formula_breakdown,
  };
}

export async function fetchBandHistory(fuelType?: string): Promise<BandHistoryEntry[]> {
  const params = fuelType ? `?fuel_type=${fuelType}` : '';
  const res = await fetch(`${API_BASE}/api/band/history${params}`);
  if (!res.ok) throw new Error('Error al obtener historial de bandas');
  const data = await res.json();
  const records = data.records || data;
  return records.map((r: Record<string, unknown>) => ({
    date: r.date,
    fuel_type: r.fuel_type,
    previous_price: r.previous_price ?? 0,
    new_price: r.price ?? r.new_price ?? 0,
    change_percent: r.change_pct ?? r.change_percent ?? 0,
    direction: ((r.change_pct ?? r.change_percent ?? 0) as number) > 0 ? 'SUBE' : ((r.change_pct ?? r.change_percent ?? 0) as number) < 0 ? 'BAJA' : 'IGUAL',
    band_applied: r.band_status !== 'DENTRO' && r.band_status !== 'LIBRE',
  }));
}

export async function fetchLatestPrices(): Promise<{
  success: boolean;
  message: string;
  source: string | null;
  date?: string;
  prices: Record<string, number>;
  saved: string[];
  predictions_updated: number;
  hint?: string;
}> {
  const res = await fetch(`${API_BASE}/api/prices/fetch-latest`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al obtener precios automaticamente');
  }
  return res.json();
}

export async function fetchNews(): Promise<NewsArticle[]> {
  const res = await fetch(`${API_BASE}/api/news`);
  if (!res.ok) throw new Error('Error al obtener noticias');
  const data = await res.json();
  const articles = data.articles || data;
  return articles.map((a: Record<string, unknown>) => ({
    title: a.title || '',
    source: a.source || '',
    url: a.url || '',
    date: a.published_relative || a.published || a.date || '',
    sentiment: typeof a.sentiment === 'object' && a.sentiment
      ? (a.sentiment as Record<string, unknown>).label || 'neutro'
      : a.sentiment || 'neutro',
    summary: a.description || a.summary || '',
  }));
}
