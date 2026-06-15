"""Scraper automatico de precios de combustibles de Ecuador.

Fuentes (en orden de prioridad):
1. El Universo - cobertura detallada el dia 11-12
2. Expreso.ec - segunda fuente confiable
3. El Comercio - respaldo
4. Primicias.ec - respaldo

EP Petroecuador publica los precios en PDFs (no scrapeables directamente),
por lo que se usan medios de comunicacion que los republican el dia 11-12.

El scraper se ejecuta automaticamente el dia 12 de cada mes via APScheduler,
y tambien puede invocarse manualmente via endpoint /api/prices/fetch-latest.
"""

import logging
import re
import ssl
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "extra": ["extra", "ron 87", "gasolina extra", "gasolinas extra"],
    "ecopais": ["ecopais", "ecopaís", "eco país", "gasolina ecopaís", "gasolina ecopais"],
    "super_95": ["súper", "super", "super 95", "supermaxi", "ron 95", "gasolina súper", "gasolina super"],
    "diesel": ["diésel", "diesel", "diésel prémium", "diesel premium", "diésel premium"],
}

# Palabras que indican que una linea tiene precios de combustibles
PRICE_TRIGGER_WORDS = ["galón", "galon", "precio", "combustible", "gasolina", "sube", "baja", "nueva", "vigente"]


def _get_session() -> requests.Session:
    """Session con SSL permisivo para redes corporativas."""
    session = requests.Session()

    class WeakSSLAdapter(requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs["verify"] = False
            return super().send(*args, **kwargs)

    session.mount("https://", WeakSSLAdapter())
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "es-EC,es;q=0.9",
    })
    return session


def _parse_price(text: str) -> Optional[float]:
    """Extrae un precio en USD de un texto."""
    text = text.replace(",", ".").replace("$", "").strip()
    match = re.search(r"\b(\d+\.\d{2,3})\b", text)
    if match:
        val = float(match.group(1))
        if 1.5 < val < 10.0:  # rango razonable para combustibles en Ecuador
            return round(val, 3)
    return None


def _identify_fuel(text: str) -> Optional[str]:
    """Identifica el tipo de combustible desde un texto."""
    text_lower = text.lower()
    # Prioridad: buscar primero los mas especificos
    for fuel_type in ["ecopais", "super_95", "diesel", "extra"]:
        if any(kw in text_lower for kw in FUEL_MAP[fuel_type]):
            return fuel_type
    return None


def _extract_prices_from_text(full_text: str) -> dict[str, float]:
    """Extrae precios de un bloque de texto buscando patrones precio-combustible."""
    prices = {}

    # Buscar patrones como "Extra $3.312" o "Gasolina extra: 3.312" o "extra pasara de X a 3.312"
    lines = [l.strip() for l in re.split(r"[\n\.\|]", full_text) if l.strip()]

    for line in lines:
        # Solo procesar lineas que mencionen combustibles o precios
        line_lower = line.lower()
        if not any(w in line_lower for w in ["extra", "ecopaís", "ecopais", "súper", "super", "diesel", "diésel"]):
            continue

        fuel = _identify_fuel(line)
        if fuel and fuel not in prices:
            # Buscar precio en la misma linea
            price = _parse_price(line)
            if price:
                prices[fuel] = price
                continue

            # Buscar "pasara de X a Y" o "de X a Y" - tomar el segundo valor (precio nuevo)
            to_match = re.search(r"de\s+\$?(\d+[\.,]\d+)\s+a\s+\$?(\d+[\.,]\d+)", line_lower)
            if to_match:
                new_val = float(to_match.group(2).replace(",", "."))
                if 1.5 < new_val < 10.0:
                    prices[fuel] = round(new_val, 3)

    return prices


def _scrape_article(url: str, site_name: str) -> dict[str, float]:
    """Scraping de un articulo especifico de noticias."""
    prices = {}
    try:
        session = _get_session()
        res = session.get(url, timeout=20)
        if res.status_code != 200:
            logger.warning("%s: HTTP %d para %s", site_name, res.status_code, url)
            return {}

        soup = BeautifulSoup(res.text, "html.parser")

        # Remover scripts, estilos y nav
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Extraer texto del articulo
        article = soup.find("article") or soup.find("main") or soup.body
        if not article:
            return {}

        full_text = article.get_text(" ", strip=True)
        prices = _extract_prices_from_text(full_text)

        logger.info("%s: encontrados %d precios en %s", site_name, len(prices), url)
    except Exception as e:
        logger.warning("Error scraping %s (%s): %s", site_name, url, e)

    return prices


def _find_article_url(base_url: str, site_name: str, keywords: list[str]) -> Optional[str]:
    """Busca en la homepage o seccion de economia el articulo con precios del mes actual."""
    try:
        session = _get_session()
        today = date.today()
        month_str = f"{today.year}/{today.month:02d}"

        res = session.get(base_url, timeout=15)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Buscar links con palabras clave de precios de combustibles
        search_terms = keywords + ["precio", "gasolina", "combustible", "diesel", "petroecuador"]
        candidates = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() + " " + href).lower()

            score = sum(1 for term in search_terms if term in text)
            if score >= 2:
                full_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                # Preferir URLs del mes actual
                priority = 2 if month_str in href or str(today.year) in href else 1
                candidates.append((priority * score, full_url))

        if candidates:
            candidates.sort(reverse=True)
            logger.info("%s: mejor candidato = %s", site_name, candidates[0][1])
            return candidates[0][1]

    except Exception as e:
        logger.warning("Error buscando articulo en %s: %s", site_name, e)

    return None


def _scrape_eluniverso() -> dict[str, float]:
    """El Universo - cobertura detallada de precios el dia 11-12."""
    try:
        today = date.today()
        # URL directa de busqueda
        search_url = f"https://www.eluniverso.com/buscar/?q=precios+gasolina+{today.year}"
        session = _get_session()
        res = session.get(search_url, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() + " " + href).lower()
            if ("precio" in text or "gasolina" in text) and str(today.year) in href:
                full_url = href if href.startswith("http") else f"https://www.eluniverso.com{href}"
                result = _scrape_article(full_url, "ElUniverso")
                if len(result) >= 3:
                    return result
    except Exception as e:
        logger.warning("Error en El Universo: %s", e)
    return {}


def _scrape_expreso() -> dict[str, float]:
    """Expreso.ec - segunda fuente confiable."""
    try:
        today = date.today()
        search_url = "https://www.expreso.ec/economia-y-negocios/"
        result = _find_article_url(search_url, "Expreso", ["gasolina", "diesel", "combustible"])
        if result:
            prices = _scrape_article(result, "Expreso")
            if len(prices) >= 3:
                return prices
    except Exception as e:
        logger.warning("Error en Expreso: %s", e)
    return {}


def _scrape_elcomercio() -> dict[str, float]:
    """El Comercio - respaldo."""
    try:
        search_url = "https://www.elcomercio.com/actualidad/negocios/"
        result = _find_article_url(search_url, "ElComercio", ["gasolina", "precio", "combustible"])
        if result:
            prices = _scrape_article(result, "ElComercio")
            if len(prices) >= 3:
                return prices
    except Exception as e:
        logger.warning("Error en El Comercio: %s", e)
    return {}


def _scrape_primicias() -> dict[str, float]:
    """Primicias.ec - respaldo."""
    try:
        today = date.today()
        search_url = f"https://www.primicias.ec/economia/?s=precio+gasolina+{today.year}"
        session = _get_session()
        res = session.get(search_url, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = (a.get_text() + " " + href).lower()
            if ("precio" in text or "gasolina" in text) and ("diesel" in text or "combustible" in text):
                full_url = href if href.startswith("http") else f"https://www.primicias.ec{href}"
                result = _scrape_article(full_url, "Primicias")
                if len(result) >= 3:
                    return result
    except Exception as e:
        logger.warning("Error en Primicias: %s", e)
    return {}


def fetch_latest_prices() -> dict:
    """Obtiene los precios mas recientes de combustibles en Ecuador.

    Intenta raspar articulos de noticias del dia 11-12 del mes actual.
    Los medios ecuatorianos publican rapidamente los nuevos precios de Petroecuador.

    Retorna dict con precios encontrados y metadata.
    """
    today = date.today()
    result = {
        "date": today.isoformat(),
        "prices": {},
        "source": None,
        "success": False,
        "message": "",
    }

    sources = [
        ("El Universo",  _scrape_eluniverso),
        ("Expreso.ec",   _scrape_expreso),
        ("El Comercio",  _scrape_elcomercio),
        ("Primicias.ec", _scrape_primicias),
    ]

    for source_name, scrape_fn in sources:
        try:
            prices = scrape_fn()
            if len(prices) >= 3:
                result["prices"] = prices
                result["source"] = source_name
                result["success"] = True
                result["message"] = f"Precios obtenidos de {source_name}: {len(prices)} combustibles"
                logger.info("Precios obtenidos de %s: %s", source_name, prices)
                return result
            elif prices:
                # Guardar precios parciales, seguir buscando
                result["prices"].update(prices)
                logger.info("%s: precios parciales %s", source_name, prices)
        except Exception as e:
            logger.warning("Error en fuente %s: %s", source_name, e)

    # Si hay al menos 2 precios parciales de distintas fuentes
    if len(result["prices"]) >= 2:
        result["source"] = "multiple"
        result["success"] = len(result["prices"]) >= 3
        result["message"] = f"Precios parciales: {list(result['prices'].keys())}"
        return result

    result["message"] = (
        "No se pudieron obtener precios automaticamente. "
        "Los precios se publican el dia 11 de cada mes. "
        "Registre manualmente via 'Registrar Precios'."
    )
    logger.warning("No se obtuvieron precios automaticamente")
    return result


def save_fetched_prices(prices: dict[str, float], price_date: date, db) -> dict:
    """Guarda los precios obtenidos en la BD y actualiza predicciones."""
    from app.database.models import FuelPrice
    from app.database import crud

    saved = []
    for fuel_type, new_price in prices.items():
        try:
            prev = db.query(FuelPrice).filter(
                FuelPrice.fuel_type == fuel_type,
                FuelPrice.date < price_date,
            ).order_by(FuelPrice.date.desc()).first()

            prev_price = float(prev.price) if prev else None
            change_pct = ((new_price - prev_price) / prev_price * 100) if prev_price else None

            band_status = "LIBRE"
            if fuel_type != "super_95" and prev_price:
                if change_pct >= 4.8:
                    band_status = "TECHO"
                elif change_pct <= -9.5:
                    band_status = "PISO"
                else:
                    band_status = "DENTRO"

            existing = db.query(FuelPrice).filter(
                FuelPrice.date == price_date,
                FuelPrice.fuel_type == fuel_type,
            ).first()

            if existing:
                existing.price = new_price
                existing.previous_price = prev_price
                existing.change_percent = round(change_pct, 2) if change_pct else None
                existing.band_status = band_status
            else:
                db.add(FuelPrice(
                    date=price_date,
                    fuel_type=fuel_type,
                    price=new_price,
                    previous_price=prev_price,
                    change_percent=round(change_pct, 2) if change_pct else None,
                    band_status=band_status,
                ))
            db.commit()
            saved.append(fuel_type)
        except Exception as e:
            logger.error("Error guardando precio %s: %s", fuel_type, e)
            db.rollback()

    # Actualizar predicciones con precios reales
    updated_preds = 0
    try:
        from app.database.models import Prediction
        preds = db.query(Prediction).filter(
            Prediction.target_date == price_date,
            Prediction.actual_price.is_(None),
        ).all()
        for pred in preds:
            if pred.fuel_type in prices:
                actual = prices[pred.fuel_type]
                pred.actual_price = actual
                if pred.predicted_price and pred.predicted_price > 0:
                    error = abs(actual - pred.predicted_price)
                    pred.accuracy_pct = round((1 - error / actual) * 100, 2)
                    pred.is_correct = error / actual < 0.02
        db.commit()
        updated_preds = len(preds)
    except Exception as e:
        logger.warning("Error actualizando predicciones: %s", e)

    return {"saved": saved, "predictions_updated": updated_preds}
