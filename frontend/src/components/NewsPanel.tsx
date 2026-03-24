'use client';

import { useState } from 'react';
import {
  Newspaper,
  TrendingUp,
  TrendingDown,
  Minus,
  ExternalLink,
  RefreshCw,
  Loader2,
  Filter,
} from 'lucide-react';

interface NewsPanelProps {
  articles: NewsArticle[];
  onRefresh: () => void;
  loading: boolean;
}

const sentimentConfig = {
  positivo: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-900/30',
    border: 'border-emerald-800',
    icon: TrendingUp,
    label: 'Positivo',
  },
  negativo: {
    color: 'text-red-400',
    bg: 'bg-red-900/30',
    border: 'border-red-800',
    icon: TrendingDown,
    label: 'Negativo',
  },
  neutro: {
    color: 'text-slate-400',
    bg: 'bg-slate-800/50',
    border: 'border-slate-700',
    icon: Minus,
    label: 'Neutro',
  },
};

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const config = sentimentConfig[sentiment as keyof typeof sentimentConfig] || sentimentConfig.neutro;
  const Icon = config.icon;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.color} border ${config.border}`}
    >
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

export default function NewsPanel({ articles, onRefresh, loading }: NewsPanelProps) {
  const [showAll, setShowAll] = useState(false);
  const [filterSentiment, setFilterSentiment] = useState<string>('all');

  const filtered =
    filterSentiment === 'all'
      ? articles
      : articles.filter((a) => a.sentiment === filterSentiment);

  const displayArticles = showAll ? filtered : filtered.slice(0, 6);

  // Resumen de sentimiento
  const posCount = articles.filter((a) => a.sentiment === 'positivo').length;
  const negCount = articles.filter((a) => a.sentiment === 'negativo').length;
  const neuCount = articles.filter((a) => a.sentiment === 'neutro').length;
  const total = articles.length;

  const overallSentiment =
    posCount > negCount && posCount > neuCount
      ? 'positivo'
      : negCount > posCount && negCount > neuCount
      ? 'negativo'
      : 'neutro';

  const overallConfig = sentimentConfig[overallSentiment];
  const OverallIcon = overallConfig.icon;

  return (
    <div className="space-y-4">
      {/* Resumen */}
      <div className={`rounded-xl border p-5 ${overallConfig.bg} ${overallConfig.border}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full ${overallConfig.bg} flex items-center justify-center`}>
              <OverallIcon className={`w-5 h-5 ${overallConfig.color}`} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">
                Sentimiento: {overallConfig.label}
              </h3>
              <p className="text-xs text-slate-400">
                Basado en {total} noticias recientes
              </p>
            </div>
          </div>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="btn-secondary text-xs flex items-center gap-1"
          >
            {loading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <RefreshCw className="w-3 h-3" />
            )}
            Actualizar
          </button>
        </div>

        {/* Barra de sentimiento */}
        {total > 0 && (
          <div>
            <div className="flex h-3 rounded-full overflow-hidden bg-slate-800">
              {posCount > 0 && (
                <div
                  className="bg-emerald-500 transition-all"
                  style={{ width: `${(posCount / total) * 100}%` }}
                />
              )}
              {neuCount > 0 && (
                <div
                  className="bg-slate-500 transition-all"
                  style={{ width: `${(neuCount / total) * 100}%` }}
                />
              )}
              {negCount > 0 && (
                <div
                  className="bg-red-500 transition-all"
                  style={{ width: `${(negCount / total) * 100}%` }}
                />
              )}
            </div>
            <div className="flex justify-between mt-1 text-xs text-slate-500">
              <span className="text-emerald-500">{posCount} positivas</span>
              <span>{neuCount} neutras</span>
              <span className="text-red-500">{negCount} negativas</span>
            </div>
          </div>
        )}
      </div>

      {/* Filtro */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-slate-500" />
        <span className="text-xs text-slate-500">Filtrar:</span>
        {['all', 'positivo', 'negativo', 'neutro'].map((opt) => (
          <button
            key={opt}
            onClick={() => setFilterSentiment(opt)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filterSentiment === opt
                ? 'bg-petroleo-700 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            {opt === 'all' ? 'Todas' : opt.charAt(0).toUpperCase() + opt.slice(1)}
          </button>
        ))}
      </div>

      {/* Lista de noticias */}
      <div className="space-y-2">
        {displayArticles.map((article, i) => (
          <div
            key={i}
            className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4 hover:bg-slate-800/60 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <SentimentBadge sentiment={article.sentiment} />
                  <span className="text-xs text-slate-600">{article.date}</span>
                  {article.source && (
                    <span className="text-xs text-slate-600">| {article.source}</span>
                  )}
                </div>
                <h4 className="text-sm font-medium text-white leading-snug mb-1">
                  {article.title}
                </h4>
                {article.summary && (
                  <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">
                    {article.summary}
                  </p>
                )}
              </div>
              {article.url && (
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-500 hover:text-petroleo-400 transition-colors flex-shrink-0"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>

      {filtered.length > 6 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="w-full text-center text-sm text-petroleo-400 hover:text-petroleo-300 py-2"
        >
          {showAll ? 'Mostrar menos' : `Ver todas (${filtered.length} noticias)`}
        </button>
      )}

      {filtered.length === 0 && (
        <div className="text-center text-slate-500 py-8">
          No hay noticias disponibles para este filtro.
        </div>
      )}
    </div>
  );
}
