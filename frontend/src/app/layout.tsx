import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'GasPredict Ecuador - Prediccion de Precios de Combustibles',
  description:
    'Dashboard inteligente para la prediccion de precios de gasolina en Ecuador. Analisis del sistema de bandas, predicciones con SARIMA, XGBoost y LSTM, seguimiento del WTI y noticias del sector.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
