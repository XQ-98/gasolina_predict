"""Servicio de noticias: obtiene noticias sobre combustibles en Ecuador y analiza sentimiento.

Busca noticias relevantes sobre precios de gasolina, combustibles y Petroecuador
desde Google News RSS en espanol. Analiza el sentimiento usando NLTK VADER
con un lexico financiero/energetico extendido para espanol.
"""

import logging
import re
from datetime import datetime
from html import unescape

import feedparser
import numpy as np

logger = logging.getLogger(__name__)

# Queries de busqueda para noticias relevantes en Ecuador
SEARCH_QUERIES_ES = [
    "precio gasolina Ecuador",
    "combustibles Ecuador",
    "Petroecuador precios",
    "gasolina diesel Ecuador",
    "subsidio combustible Ecuador",
    "bandas precios combustibles",
    "precio petroleo Ecuador",
]

SEARCH_QUERIES_EN = [
    "Ecuador fuel prices",
    "Ecuador gasoline price",
    "WTI crude oil price",
    "OPEC oil production",
    "oil market outlook",
]


def _clean_html(text: str) -> str:
    """Elimina tags HTML y decodifica entidades."""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _analyze_sentiment_vader(text: str) -> dict:
    """Analiza el sentimiento usando VADER con lexico financiero/energetico extendido.

    Soporta textos en espanol e ingles.
    """
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        import nltk

        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)

        sid = SentimentIntensityAnalyzer()

        # Lexico financiero/energetico
        financial_lexicon = {
            # Ingles - alcista
            "surge": 2.5, "surged": 2.5, "rally": 2.0, "rallied": 2.0,
            "soar": 2.5, "soared": 2.5, "jump": 1.5, "jumped": 1.5,
            "gain": 1.5, "gains": 1.5, "bull": 1.5, "bullish": 2.0,
            "record high": 3.0, "shortage": 1.0, "supply cut": 1.5,
            # Ingles - bajista
            "plunge": -2.5, "plunged": -2.5, "crash": -3.0, "crashed": -3.0,
            "slump": -2.0, "slumped": -2.0, "drop": -1.5, "dropped": -1.5,
            "decline": -1.5, "declined": -1.5, "bear": -1.5, "bearish": -2.0,
            "surplus": -1.0, "oversupply": -1.5, "weak": -1.5,
            # Espanol - alcista (precios suben = negativo para consumidor)
            "sube": 1.5, "subio": 1.5, "alza": 2.0, "incremento": 1.5,
            "encarece": 2.0, "aumento": 1.5, "elevado": 1.0,
            # Espanol - bajista (precios bajan = positivo para consumidor)
            "baja": -1.5, "bajo": -1.5, "reduccion": -1.5, "abarata": -2.0,
            "descenso": -1.5, "disminuye": -1.5,
            # Espanol - neutral/politico
            "subsidio": 0.5, "decreto": 0.0, "protesta": -1.0,
            "congelamiento": -0.5, "banda": 0.0, "revision": 0.0,
        }
        sid.lexicon.update(financial_lexicon)

        scores = sid.polarity_scores(text)
        compound = scores["compound"]

        if compound >= 0.15:
            label = "positivo"
            impact = "alcista"
        elif compound <= -0.15:
            label = "negativo"
            impact = "bajista"
        else:
            label = "neutro"
            impact = "neutral"

        return {
            "score": round(compound, 3),
            "label": label,
            "impact": impact,
            "confidence": round(abs(compound), 2),
        }
    except ImportError:
        return _analyze_sentiment_basic(text)


def _analyze_sentiment_basic(text: str) -> dict:
    """Analisis de sentimiento basico por keywords (sin NLTK)."""
    text_lower = text.lower()

    positive_words = [
        "sube", "subio", "alza", "incremento", "encarece", "aumento",
        "surge", "surged", "rally", "jump", "gain", "higher", "record",
        "shortage", "supply cut", "bullish",
    ]
    negative_words = [
        "baja", "bajo", "reduccion", "abarata", "descenso", "disminuye",
        "plunge", "crash", "slump", "drop", "decline", "lower",
        "surplus", "oversupply", "bearish", "weak",
    ]

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return {"score": 0.0, "label": "neutro", "impact": "neutral", "confidence": 0.0}

    score = (pos_count - neg_count) / total
    if score > 0.2:
        label, impact = "positivo", "alcista"
    elif score < -0.2:
        label, impact = "negativo", "bajista"
    else:
        label, impact = "neutro", "neutral"

    return {
        "score": round(score, 3),
        "label": label,
        "impact": impact,
        "confidence": round(abs(score), 2),
    }


def fetch_news(max_articles: int = 15, lang: str = "es") -> list[dict]:
    """Obtiene noticias sobre combustibles en Ecuador desde Google News RSS.

    Args:
        max_articles: Numero maximo de articulos a retornar.
        lang: Idioma ("es" para espanol, "en" para ingles).

    Returns:
        Lista de noticias con titulo, descripcion, fuente, fecha y sentimiento.
    """
    queries = SEARCH_QUERIES_ES if lang == "es" else SEARCH_QUERIES_EN
    hl = "es-419" if lang == "es" else "en-US"
    gl = "EC" if lang == "es" else "US"
    ceid = f"{gl}:{lang}"

    all_articles = []
    seen_titles = set()

    for query in queries:
        try:
            url = (
                f"https://news.google.com/rss/search?"
                f"q={query.replace(' ', '+')}&hl={hl}&gl={gl}&ceid={ceid}"
            )
            feed = feedparser.parse(url)

            for entry in feed.entries[:5]:
                title = _clean_html(entry.get("title", ""))

                # Deduplicar por titulo similar
                title_key = title.lower()[:60]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                description = _clean_html(
                    entry.get("summary", entry.get("description", ""))
                )
                published = entry.get("published", "")
                source = entry.get("source", {}).get("title", "")
                link = entry.get("link", "")

                # Parsear fecha
                try:
                    pub_date = (
                        datetime(*entry.published_parsed[:6])
                        if entry.get("published_parsed")
                        else None
                    )
                except Exception:
                    pub_date = None

                # Analizar sentimiento del titulo + descripcion
                full_text = f"{title}. {description}"
                sentiment = _analyze_sentiment_vader(full_text)

                all_articles.append({
                    "title": title,
                    "description": description[:300] if description else "",
                    "source": source,
                    "url": link,
                    "published": pub_date.isoformat() if pub_date else published,
                    "published_relative": _relative_time(pub_date) if pub_date else "",
                    "sentiment": sentiment,
                })
        except Exception as e:
            logger.warning(f"Error obteniendo noticias para '{query}': {e}")
            continue

    # Ordenar por fecha (mas recientes primero)
    all_articles.sort(key=lambda x: x.get("published", ""), reverse=True)

    return all_articles[:max_articles]


def _relative_time(dt: datetime) -> str:
    """Convierte una fecha a tiempo relativo (ej: 'hace 2 horas')."""
    if dt is None:
        return ""
    now = datetime.utcnow()
    diff = now - dt

    if diff.days > 30:
        return f"hace {diff.days // 30} meses"
    elif diff.days > 0:
        return f"hace {diff.days} dias"
    elif diff.seconds > 3600:
        return f"hace {diff.seconds // 3600} horas"
    elif diff.seconds > 60:
        return f"hace {diff.seconds // 60} minutos"
    else:
        return "hace un momento"


def get_sentiment_summary(articles: list[dict]) -> dict:
    """Genera un resumen del sentimiento general de las noticias.

    Returns:
        Dict con sentimiento promedio, distribucion y senal para el precio.
    """
    if not articles:
        return {
            "overall_score": 0,
            "overall_label": "Sin datos",
            "signal": "neutral",
            "distribution": {"positivo": 0, "neutro": 0, "negativo": 0},
            "total_articles": 0,
            "summary": "No se encontraron noticias recientes sobre combustibles en Ecuador.",
        }

    scores = [a["sentiment"]["score"] for a in articles]
    labels = [a["sentiment"]["label"] for a in articles]

    avg_score = float(np.mean(scores))
    distribution = {
        "positivo": labels.count("positivo"),
        "neutro": labels.count("neutro"),
        "negativo": labels.count("negativo"),
    }

    if avg_score >= 0.15:
        overall_label = "Positivo"
        signal = "alcista"
        tendency = "subir"
    elif avg_score <= -0.15:
        overall_label = "Negativo"
        signal = "bajista"
        tendency = "bajar"
    else:
        overall_label = "Neutro"
        signal = "neutral"
        tendency = "mantenerse estable"

    total = len(articles)
    pos_pct = round(distribution["positivo"] / total * 100)
    neg_pct = round(distribution["negativo"] / total * 100)

    summary = (
        f"De {total} noticias analizadas, {pos_pct}% son positivas y {neg_pct}% negativas. "
        f"El sentimiento general es {overall_label.lower()}, "
        f"lo que sugiere que los precios de combustibles podrian {tendency} en el corto plazo."
    )

    return {
        "overall_score": round(avg_score, 3),
        "overall_label": overall_label,
        "signal": signal,
        "distribution": distribution,
        "total_articles": total,
        "summary": summary,
    }
