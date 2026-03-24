'use client';

import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface PredictionChartProps {
  prediction: PredictionResult;
  historicalData: HistoricalPrice[];
  fuelType: string;
}

const fuelColors: Record<string, string> = {
  extra: '#14b8a6',
  ecopais: '#84cc16',
  super_95: '#f59e0b',
  diesel: '#ef4444',
};

const fuelLabels: Record<string, string> = {
  extra: 'Extra',
  ecopais: 'EcoPais',
  super_95: 'Super 95',
  diesel: 'Diesel',
};

export default function PredictionChart({
  prediction,
  historicalData,
  fuelType,
}: PredictionChartProps) {
  const color = fuelColors[fuelType] || '#14b8a6';
  const label = fuelLabels[fuelType] || fuelType;

  // Ultimos 12 meses historicos
  const recent = historicalData.slice(-12);
  const historicalDates = recent.map((d) => d.date);
  const historicalPrices = recent.map((d) => (d as any)[fuelType] as number);

  // Predicciones
  const predDates = prediction.predictions.map((p) => p.month);
  const predPrices = prediction.predictions.map((p) => p.predicted_price);
  const lowerBounds = prediction.predictions.map((p) => p.lower_bound);
  const upperBounds = prediction.predictions.map((p) => p.upper_bound);

  const traces: any[] = [
    // Historico
    {
      x: historicalDates,
      y: historicalPrices,
      type: 'scatter',
      mode: 'lines+markers',
      name: `Historico (${label})`,
      line: { color, width: 2 },
      marker: { size: 5 },
    },
    // Prediccion
    {
      x: predDates,
      y: predPrices,
      type: 'scatter',
      mode: 'lines+markers',
      name: `Prediccion (${label})`,
      line: { color: '#22c55e', width: 2, dash: 'dash' },
      marker: { size: 6, symbol: 'diamond' },
      hovertemplate:
        'Fecha: %{x}<br>Prediccion: $%{y:.2f}/gal<extra></extra>',
    },
    // Intervalo de confianza
    {
      x: [...predDates, ...predDates.slice().reverse()],
      y: [...upperBounds, ...lowerBounds.slice().reverse()],
      type: 'scatter',
      fill: 'toself',
      fillcolor: 'rgba(34, 197, 94, 0.1)',
      line: { color: 'transparent' },
      name: 'Intervalo de confianza 95%',
      showlegend: true,
      hoverinfo: 'skip',
    },
  ];

  // Marcadores de estado de banda
  const bandColors: Record<string, string> = {
    TECHO: '#ef4444',
    PISO: '#22c55e',
    DENTRO: '#f59e0b',
  };

  const bandAnnotations = prediction.predictions.map((p) => ({
    x: p.month,
    y: p.predicted_price,
    text: p.band_status === 'TECHO' ? 'T' : p.band_status === 'PISO' ? 'P' : '',
    showarrow: false,
    font: {
      size: 9,
      color: bandColors[p.band_status] || '#94a3b8',
    },
    yshift: 15,
  })).filter((a) => a.text !== '');

  return (
    <Plot
      data={traces}
      layout={{
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: '#94a3b8' },
        xaxis: {
          gridcolor: '#334155',
          title: { text: 'Mes (dia 11)' },
          tickformat: '%b %Y',
        },
        yaxis: {
          gridcolor: '#334155',
          title: { text: 'Precio (USD/galon)' },
        },
        legend: {
          x: 0,
          y: 1.15,
          orientation: 'h',
          font: { size: 11 },
        },
        margin: { l: 60, r: 20, t: 10, b: 50 },
        shapes: [
          {
            type: 'line',
            x0: predDates[0],
            x1: predDates[0],
            y0: 0,
            y1: 1,
            yref: 'paper',
            line: { color: '#64748b', width: 1, dash: 'dot' },
          },
        ],
        annotations: [
          {
            x: predDates[0],
            y: 1.05,
            yref: 'paper',
            text: 'Inicio prediccion',
            showarrow: false,
            font: { color: '#94a3b8', size: 11 },
          },
          ...bandAnnotations,
        ],
        hovermode: 'x unified',
      }}
      config={{ responsive: true, displayModeBar: false }}
      style={{ width: '100%', height: '450px' }}
    />
  );
}
