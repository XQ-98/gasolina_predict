'use client';

import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface HistoricalChartProps {
  data: HistoricalPrice[];
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

export default function HistoricalChart({ data }: HistoricalChartProps) {
  const dates = data.map((d) => d.date);

  const fuelTraces: any[] = [
    {
      x: dates,
      y: data.map((d) => d.extra),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Extra',
      line: { color: fuelColors.extra, width: 2 },
      marker: { size: 4 },
      hovertemplate: 'Fecha: %{x}<br>Extra: $%{y:.2f}/gal<extra></extra>',
    },
    {
      x: dates,
      y: data.map((d) => d.ecopais),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'EcoPais',
      line: { color: fuelColors.ecopais, width: 2 },
      marker: { size: 4 },
      hovertemplate: 'Fecha: %{x}<br>EcoPais: $%{y:.2f}/gal<extra></extra>',
    },
    {
      x: dates,
      y: data.map((d) => d.super_95),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Super 95',
      line: { color: fuelColors.super_95, width: 2 },
      marker: { size: 4 },
      hovertemplate: 'Fecha: %{x}<br>Super 95: $%{y:.2f}/gal<extra></extra>',
    },
    {
      x: dates,
      y: data.map((d) => d.diesel),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Diesel',
      line: { color: fuelColors.diesel, width: 2 },
      marker: { size: 4 },
      hovertemplate: 'Fecha: %{x}<br>Diesel: $%{y:.2f}/gal<extra></extra>',
    },
  ];

  // WTI en eje Y secundario
  const wtiTrace = {
    x: dates,
    y: data.map((d) => d.wti),
    type: 'scatter',
    mode: 'lines',
    name: 'WTI (USD/barril)',
    line: { color: '#94a3b8', width: 1.5, dash: 'dot' },
    yaxis: 'y2',
    hovertemplate: 'Fecha: %{x}<br>WTI: $%{y:.2f}/bbl<extra></extra>',
  };

  return (
    <Plot
      data={[...fuelTraces, wtiTrace]}
      layout={{
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { color: '#94a3b8' },
        xaxis: {
          gridcolor: '#334155',
          title: { text: 'Fecha (dia 11 de cada mes)' },
          tickformat: '%b %Y',
        },
        yaxis: {
          gridcolor: '#334155',
          title: { text: 'Precio (USD/galon)' },
          side: 'left',
        },
        yaxis2: {
          title: { text: 'WTI (USD/barril)', font: { color: '#94a3b8' } },
          overlaying: 'y',
          side: 'right',
          showgrid: false,
          tickfont: { color: '#94a3b8' },
        },
        legend: {
          x: 0,
          y: 1.15,
          orientation: 'h',
          font: { size: 11 },
        },
        margin: { l: 60, r: 60, t: 10, b: 50 },
        hovermode: 'x unified',
      }}
      config={{ responsive: true, displayModeBar: false }}
      style={{ width: '100%', height: '450px' }}
    />
  );
}
