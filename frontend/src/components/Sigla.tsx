'use client';

const glossary: Record<string, string> = {
  WTI: 'West Texas Intermediate — Precio de referencia del petroleo crudo en EE.UU. Se usa como base para calcular el costo de importacion de gasolina en Ecuador.',
  IC: 'Intervalo de Confianza — Rango estadistico donde se espera que caiga el valor real con un 95% de probabilidad.',
  avg: 'Average (Promedio) — Valor medio calculado sobre un conjunto de datos.',
  CIF: 'Cost, Insurance and Freight (Costo, Seguro y Flete) — Precio de importacion que incluye el producto, seguro de transporte y flete maritimo hasta Ecuador.',
  SARIMA: 'Seasonal ARIMA — Modelo estadistico de series de tiempo que captura tendencias y patrones estacionales.',
  XGBoost: 'Extreme Gradient Boosting — Algoritmo de Machine Learning basado en arboles de decision que aprende de errores anteriores.',
  LSTM: 'Long Short-Term Memory — Red neuronal profunda especializada en aprender patrones en secuencias de datos.',
  MAPE: 'Mean Absolute Percentage Error — Error promedio del modelo expresado en porcentaje. Menor valor = mejor prediccion.',
  RMSE: 'Root Mean Square Error — Raiz del error cuadratico medio. Penaliza mas los errores grandes.',
  MAE: 'Mean Absolute Error — Error absoluto promedio medido en dolares.',
  RON: 'Research Octane Number — Indice de octanaje que mide la capacidad antidetonante de la gasolina.',
  EP: 'EP Petroecuador — Empresa Publica de Hidrocarburos del Ecuador, encargada de refinar e importar combustibles.',
};

export default function Sigla({ term, children }: { term: string; children?: React.ReactNode }) {
  const meaning = glossary[term];
  if (!meaning) return <span>{children || term}</span>;
  return (
    <span className="relative group/tip inline-flex items-center gap-0.5">
      <span className="border-b border-dotted border-slate-500 cursor-help">
        {children || term}
      </span>
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-xs text-slate-200 whitespace-normal w-64 text-center opacity-0 invisible group-hover/tip:opacity-100 group-hover/tip:visible transition-all duration-200 z-50 shadow-lg pointer-events-none leading-relaxed">
        <strong className="text-white block mb-0.5">{term}</strong>
        {meaning}
      </span>
    </span>
  );
}

export { glossary };
