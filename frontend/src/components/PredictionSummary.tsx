'use client';

import { TrendingUp, TrendingDown, ArrowRight, AlertTriangle } from 'lucide-react';

interface PredictionSummaryProps {
  prediction: PredictionResult;
  currentPrice: number;
}

const fuelLabels: Record<string, string> = {
  extra: 'Extra',
  ecopais: 'EcoPais',
  super_95: 'Super 95',
  diesel: 'Diesel',
};

export default function PredictionSummary({ prediction, currentPrice }: PredictionSummaryProps) {
  const preds = prediction.predictions;
  if (!preds || preds.length === 0) return null;

  const lastPred = preds[preds.length - 1];
  const midPred = preds[Math.floor(preds.length / 2)];
  const label = fuelLabels[prediction.fuel_type] || prediction.fuel_type;

  const change = lastPred.predicted_price - currentPrice;
  const changePct = currentPrice > 0 ? (change / currentPrice) * 100 : 0;
  const isUp = change > 0;

  const changeMid = midPred.predicted_price - currentPrice;
  const changeMidPct = currentPrice > 0 ? (changeMid / currentPrice) * 100 : 0;
  const isMidUp = changeMid > 0;

  // Tendencia
  const firstHalf = preds.slice(0, Math.floor(preds.length / 2));
  const secondHalf = preds.slice(Math.floor(preds.length / 2));
  const avgFirst = firstHalf.reduce((a, b) => a + b.predicted_price, 0) / (firstHalf.length || 1);
  const avgSecond = secondHalf.reduce((a, b) => a + b.predicted_price, 0) / (secondHalf.length || 1);
  const trendUp = avgSecond > avgFirst;

  // Confianza
  const lastUpper = lastPred.upper_bound;
  const lastLower = lastPred.lower_bound;
  const uncertainty = lastPred.predicted_price > 0
    ? ((lastUpper - lastLower) / lastPred.predicted_price) * 100
    : 0;

  let confidence: string;
  let confidenceColor: string;
  if (uncertainty < 5) {
    confidence = 'Alta';
    confidenceColor = 'text-emerald-400';
  } else if (uncertainty < 15) {
    confidence = 'Moderada';
    confidenceColor = 'text-yellow-400';
  } else {
    confidence = 'Baja';
    confidenceColor = 'text-red-400';
  }

  // Bandas
  const techoCount = preds.filter((p) => p.band_status === 'TECHO').length;
  const pisoCount = preds.filter((p) => p.band_status === 'PISO').length;

  const minPred = Math.min(...preds.map((p) => p.predicted_price));
  const maxPred = Math.max(...preds.map((p) => p.predicted_price));

  return (
    <div className="space-y-4">
      {/* Veredicto principal */}
      <div
        className={`rounded-xl border p-6 ${
          isUp
            ? 'bg-red-900/20 border-red-800'
            : 'bg-emerald-900/20 border-emerald-800'
        }`}
      >
        <div className="flex items-center gap-3 mb-3">
          {isUp ? (
            <div className="w-12 h-12 rounded-full bg-red-900/50 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-red-400" />
            </div>
          ) : (
            <div className="w-12 h-12 rounded-full bg-emerald-900/50 flex items-center justify-center">
              <TrendingDown className="w-6 h-6 text-emerald-400" />
            </div>
          )}
          <div>
            <h3 className="text-lg font-bold text-white">
              {label}: El precio {isUp ? 'SUBE' : 'BAJA'}
            </h3>
            <p className="text-sm text-slate-400">
              Proyeccion a {preds.length} {preds.length === 1 ? 'mes' : 'meses'}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          <div>
            <span className="text-xs text-slate-500 block">Precio actual</span>
            <span className="text-lg font-semibold text-white">
              ${currentPrice.toFixed(2)}
            </span>
            <span className="text-xs text-slate-500 block">USD/galon</span>
          </div>
          <div>
            <span className="text-xs text-slate-500 block">Precio proyectado</span>
            <span
              className={`text-lg font-semibold ${
                isUp ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              ${lastPred.predicted_price.toFixed(2)}
            </span>
            <span className="text-xs text-slate-500 block">USD/galon</span>
          </div>
          <div>
            <span className="text-xs text-slate-500 block">Variacion</span>
            <span
              className={`text-lg font-semibold ${
                isUp ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {isUp ? '+' : ''}
              {changePct.toFixed(1)}%
            </span>
            <span className={`text-xs ${isUp ? 'text-red-500' : 'text-emerald-500'}`}>
              {isUp ? '+' : ''}${Math.abs(change).toFixed(3)}
            </span>
          </div>
          <div>
            <span className="text-xs text-slate-500 block">Confianza</span>
            <span className={`text-lg font-semibold ${confidenceColor}`}>
              {confidence}
            </span>
            <span className="text-xs text-slate-500 block">
              Rango: {'\u00B1'}{(uncertainty / 2).toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Detalle */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Rango proyectado</h4>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-500">Min</span>
              <p className="text-sm font-medium text-slate-300">${minPred.toFixed(2)}</p>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-600" />
            <div className="text-right">
              <span className="text-xs text-slate-500">Max</span>
              <p className="text-sm font-medium text-slate-300">${maxPred.toFixed(2)}</p>
            </div>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-2">A mitad de periodo</h4>
          <div className="flex items-center gap-2">
            {isMidUp ? (
              <TrendingUp className="w-4 h-4 text-red-400" />
            ) : (
              <TrendingDown className="w-4 h-4 text-emerald-400" />
            )}
            <span className={`text-sm font-medium ${isMidUp ? 'text-red-400' : 'text-emerald-400'}`}>
              {isMidUp ? '+' : ''}{changeMidPct.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-500">
              (${midPred.predicted_price.toFixed(2)})
            </span>
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Tendencia</h4>
          <div className="flex items-center gap-2">
            {trendUp ? (
              <TrendingUp className="w-4 h-4 text-red-400" />
            ) : (
              <TrendingDown className="w-4 h-4 text-emerald-400" />
            )}
            <span className={`text-sm font-medium ${trendUp ? 'text-red-400' : 'text-emerald-400'}`}>
              {trendUp ? 'Alcista' : 'Bajista'}
            </span>
            <span className="text-xs text-slate-500">en la segunda mitad</span>
          </div>
        </div>
      </div>

      {/* Alerta de bandas */}
      {(techoCount > 0 || pisoCount > 0) && (
        <div className="bg-amber-900/10 border border-amber-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h4 className="text-xs text-amber-500 uppercase tracking-wider font-medium">
              Sistema de bandas activo
            </h4>
          </div>
          <p className="text-sm text-slate-400">
            {techoCount > 0 &&
              `En ${techoCount} ${techoCount === 1 ? 'mes' : 'meses'} se topa con el techo de la banda (+5%). `}
            {pisoCount > 0 &&
              `En ${pisoCount} ${pisoCount === 1 ? 'mes' : 'meses'} se topa con el piso de la banda (-10%). `}
            El precio final sera limitado por el sistema de bandas del gobierno.
          </p>
        </div>
      )}

      {/* Detalle del enfoque de 2 capas */}
      {prediction.approach === 'two_layer' && prediction.layer_1_wti && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-blue-900/50 flex items-center justify-center">
              <span className="text-xs font-bold text-blue-400">2L</span>
            </div>
            <h4 className="text-sm font-semibold text-white">
              Prediccion de 2 Capas
            </h4>
            <span className="text-xs bg-blue-900/30 text-blue-400 px-2 py-0.5 rounded-full">
              Mas preciso
            </span>
          </div>

          {/* Capa 1: WTI */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <h5 className="text-xs text-slate-500 uppercase tracking-wider mb-3 font-medium">
              Capa 1: Prediccion del WTI
            </h5>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <span className="text-xs text-slate-500 block">WTI Actual</span>
                <span className="text-sm font-semibold text-white">
                  ${prediction.layer_1_wti.wti_current?.toFixed(2) ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">WTI Predicho (avg)</span>
                <span className={`text-sm font-semibold ${
                  prediction.layer_1_wti.wti_change_pct > 0 ? 'text-red-400' : 'text-emerald-400'
                }`}>
                  ${prediction.layer_1_wti.wti_predicted_avg?.toFixed(2) ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Cambio WTI</span>
                <span className={`text-sm font-semibold ${
                  prediction.layer_1_wti.wti_change_pct > 0 ? 'text-red-400' : 'text-emerald-400'
                }`}>
                  {prediction.layer_1_wti.wti_change_pct > 0 ? '+' : ''}
                  {prediction.layer_1_wti.wti_change_pct?.toFixed(2) ?? 0}%
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Datos usados</span>
                <span className="text-sm font-semibold text-white">
                  {prediction.layer_1_wti.data_points_used?.toLocaleString() ?? '—'} dias
                </span>
              </div>
            </div>
            <div className="mt-3 flex gap-4 text-xs text-slate-500">
              <span>
                IC 95%: ${prediction.layer_1_wti.confidence_interval?.lower?.toFixed(2) ?? '—'}
                — ${prediction.layer_1_wti.confidence_interval?.upper?.toFixed(2) ?? '—'}
              </span>
              {prediction.layer_1_wti.weights && (
                <span>
                  Pesos: SARIMA {((prediction.layer_1_wti.weights.sarima ?? 0) * 100).toFixed(0)}% |
                  XGBoost {((prediction.layer_1_wti.weights.xgboost ?? 0) * 100).toFixed(0)}% |
                  LSTM {((prediction.layer_1_wti.weights.lstm ?? 0) * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>

          {/* Capa 2: Formula */}
          {prediction.layer_2_formula && (
            <div className="bg-slate-900/50 rounded-lg p-4">
              <h5 className="text-xs text-slate-500 uppercase tracking-wider mb-3 font-medium">
                Capa 2: Formula Decreto 308 + Banda
              </h5>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <span className="text-xs text-slate-500 block">Precio teorico</span>
                  <span className="text-sm font-semibold text-slate-300">
                    ${prediction.layer_2_formula.theoretical_price?.toFixed(3) ?? '—'}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Banda aplicada</span>
                  <span className={`text-sm font-semibold ${
                    preds[0]?.band_status === 'TECHO' ? 'text-red-400'
                    : preds[0]?.band_status === 'PISO' ? 'text-emerald-400'
                    : 'text-yellow-400'
                  }`}>
                    {preds[0]?.band_status ?? 'DENTRO'}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Precio final</span>
                  <span className="text-sm font-bold text-white">
                    ${lastPred.predicted_price?.toFixed(3) ?? '—'}
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-600 mt-2 italic">
                WTI predicho → formula del gobierno → techo +5% / piso -10% → precio final
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
