interface FuelPrice {
  type: 'extra' | 'ecopais' | 'super_95' | 'diesel';
  name: string;
  price_per_gallon: number;
  previous_price: number;
  change_percent: number;
  change_direction: 'SUBE' | 'BAJA' | 'IGUAL';
  effective_date: string;
  band_applied: 'TECHO' | 'PISO' | 'DENTRO' | 'LIBRE';
}

interface HistoricalPrice {
  date: string;
  extra: number;
  ecopais: number;
  super_95: number;
  diesel: number;
  wti: number;
}

interface PredictionResult {
  fuel_type: string;
  predictions: MonthlyPrediction[];
  models: ModelPredictions;
  metrics: ModelMetrics;
  confidence_intervals: ConfidenceInterval[];
  approach?: 'two_layer' | 'ensemble' | 'demo';
  layer_1_wti?: {
    wti_predicted_avg: number;
    wti_current: number;
    wti_change_pct: number;
    confidence_interval: { lower: number; upper: number };
    daily_predictions: { date: string; price: number }[];
    weights: Record<string, number>;
    metrics: Record<string, { rmse: number; mae: number; mape: number }>;
    data_points_used: number;
  };
  layer_2_formula?: {
    theoretical_price: number;
    formula_breakdown: Record<string, number>;
  };
}

interface MonthlyPrediction {
  month: string;
  predicted_price: number;
  lower_bound: number;
  upper_bound: number;
  band_status: 'TECHO' | 'PISO' | 'DENTRO';
  change_from_current: number;
}

interface ModelPredictions {
  sarima: number[];
  xgboost: number[];
  lstm: number[];
  ensemble: number[];
  dates: string[];
  weights: Record<string, number>;
}

interface ModelMetrics {
  [model: string]: {
    rmse: number;
    mae: number;
    mape: number;
    error?: string;
  };
}

interface ConfidenceInterval {
  date: string;
  lower: number;
  upper: number;
  predicted: number;
}

interface BandSimulation {
  current_price: number;
  theoretical_price: number;
  band_result: number;
  band_status: 'TECHO' | 'PISO' | 'DENTRO';
  max_possible: number;
  min_possible: number;
  wti_price: number;
  formula_breakdown?: Record<string, number>;
}

interface BandHistoryEntry {
  date: string;
  fuel_type: string;
  previous_price: number;
  new_price: number;
  change_percent: number;
  direction: 'SUBE' | 'BAJA' | 'IGUAL';
  band_applied: boolean;
}

interface NewsArticle {
  title: string;
  source: string;
  url: string;
  date: string;
  sentiment: 'positivo' | 'negativo' | 'neutro';
  summary?: string;
}

interface AnalysisData {
  factors: AnalysisFactor[];
  summary: string;
  current_prices: FuelPrice[];
}

interface AnalysisFactor {
  factor: string;
  value: number;
  impact: 'alto' | 'medio' | 'bajo';
  direction: 'positivo' | 'negativo' | 'neutro';
  description: string;
}

interface WtiData {
  current: number;
  change_24h: number;
  change_7d: number;
  change_30d: number;
  historical: { date: string; price: number }[];
}
