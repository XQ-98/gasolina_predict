'use client';

import { TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';

interface AnalysisPanelProps {
  analysis: AnalysisData;
}

const impactColors: Record<string, { bar: string; text: string; width: string }> = {
  alto: { bar: 'bg-red-500', text: 'text-red-400', width: 'w-full' },
  medio: { bar: 'bg-gasolina-500', text: 'text-gasolina-400', width: 'w-2/3' },
  bajo: { bar: 'bg-emerald-500', text: 'text-emerald-400', width: 'w-1/3' },
};

const directionConfig: Record<string, { icon: typeof TrendingUp; color: string; label: string }> = {
  positivo: { icon: TrendingUp, color: 'text-red-400', label: 'Presion al alza' },
  negativo: { icon: TrendingDown, color: 'text-emerald-400', label: 'Presion a la baja' },
  neutro: { icon: Minus, color: 'text-slate-400', label: 'Neutral' },
};

export default function AnalysisPanel({ analysis }: AnalysisPanelProps) {
  return (
    <div className="space-y-4">
      {/* Resumen */}
      <div className="bg-slate-700/50 rounded-lg p-4">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-petroleo-400 flex-shrink-0 mt-0.5" />
          <p className="text-slate-300 text-sm leading-relaxed">{analysis.summary}</p>
        </div>
      </div>

      {/* Factores */}
      <div className="space-y-3">
        {analysis.factors.map((factor, idx) => {
          const impact = impactColors[factor.impact] || impactColors.bajo;
          const direction = directionConfig[factor.direction] || directionConfig.neutro;
          const Icon = direction.icon;

          return (
            <div
              key={idx}
              className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${direction.color}`} />
                  <span className="font-medium text-slate-200">{factor.factor}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${direction.color}`}>
                    {direction.label}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    factor.impact === 'alto'
                      ? 'bg-red-900/30 text-red-400'
                      : factor.impact === 'medio'
                      ? 'bg-gasolina-900/30 text-gasolina-400'
                      : 'bg-emerald-900/30 text-emerald-400'
                  }`}>
                    Impacto {factor.impact}
                  </span>
                </div>
              </div>

              <p className="text-sm text-slate-400 mb-3">{factor.description}</p>

              {/* Barra de impacto */}
              <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${impact.bar} transition-all`}
                  style={{
                    width: factor.impact === 'alto' ? '100%' : factor.impact === 'medio' ? '66%' : '33%',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {analysis.factors.length === 0 && (
        <div className="text-center text-slate-500 py-8">
          No se identificaron factores significativos en este periodo.
        </div>
      )}
    </div>
  );
}
