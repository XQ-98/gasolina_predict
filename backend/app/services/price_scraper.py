"""Scraper automatico de precios de combustibles de Ecuador.

Fuentes (en orden de prioridad):
1. EP Petroecuador - fuente oficial
2. Metro Ecuador - noticias confiables dia 11-12
3. Expreso.ec - respaldo

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
    "extra": ["extra", "ron 87", "gasolina extra"],
    "ecopais": ["ecopais", "ecopaís", "eco país"],
    "super_95": ["super", "super 95", "supermaxi", "ron 95"],
    "diesel": ["diesel", "diésel", "diesel premium"],
}

def _get_session() -> requests.Session:
    """Session con SSL permisivo para redes corporativas."""
    session = requests.Session()
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=0")
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    class WeakSSLAdapter(requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs["verify"] = False
            return super().send(*args, **kwargs)

    session.mount("https://", WeakSSLAdapter())
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session


def _parse_price(text: str) -> Optional[float]:
    """Extrae un precio en USD de un texto."""
    text = text.replace(",", ".").replace("$", "").strip()
    match = re.search(r"\b(\d+\.\d{2,3})\b", text)
    if match:
        val = float(match.group(1))
        if 1.0 < val < 15.0:  # rango razonable para combustibles en Ecuador
            return round(val, 3)
    return None


def _identify_fuel(text: str) -> Optional[str]:
    """Identifica el tipo de combustible desde un texto."""
    text_lower = text.lower()
    for fuel_type, keywords in FUEL_MAP.items():
        if any(kw in text_lower for kw in keywords):
            return fuel_type
    return None


def _scrape_petroecuador() -> dict[str, float]:
    """Scraping de EP Petroecuador (fuente oficial)."""
    prices = {}
    try:
        session = _get_session()
        res = session.get("https://www.eppetroecuador.ec/?p=8062", timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        # Buscar tablas con precios
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                text = " ".join(cells)
                fuel = _identify_fuel(text)
                if fuel and fuel not in prices:
                    for cell in cells:
                        price = _parse_price(cell)
                        if price:
                            prices[fuel] = price
                            break

        # Buscar en parrafos si no hay tabla
        if not prices:
            for p in soup.find_all(["p", "li", "td", "span"]):
                text = p.get_text(strip=True)
                fuel = _identify_fuel(text)
                if fuel and fuel not in prices:
                    price = _parse_price(text)
                    if price:
                        prices[fuel] = price

        logger.info("Petroecuador: encontrados %d precios", len(prices))
    except Exception as e:
        logger.warning("Error scraping Petroecuador: %s", e)

    return prices


def _scrape_news_site(url: str, site_name: str) -> dict[str, float]:
    """Scraping generico de sitios de noticias."""
    prices = {}
    try:
        session = _get_session()
        res = session.get(url, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        # Buscar en todo el texto de la pagina
        full_text = soup.get_text(" ", strip=True)
        lines = [l.strip() for l in full_text.split("\n") if l.strip()]

        for line in lines:
            fuel = _identify_fuel(line)
            if fuel and fuel not in prices:
                price = _parse_price(line)
                if price:
                    prices[fuel] = price

        logger.info("%s: encontrados %d precios", site_name, len(prices))
    except Exception as e:
        logger.warning("Error scraping %s: %s", site_name, e)

    return prices


def _scrape_metro_ecuador() -> dict[str, float]:
    """Scraping de Metro Ecuador - busca el articulo del mes actual."""
    try:
        today = date.today()
        # Construir URL del articulo del mes actual
        urls_to_try = [
            f"https://www.metroecuador.com.ec/noticias/{today.year}/{today.month:02d}/",
            "https://www.metroecuador.com.ec/noticias/",
        ]
        session = _get_session()
        for base_url in urls_to_try:
            try:
                res = session.get(base_url, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                # Buscar links con "precio" y "gasolina" o "combustible"
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text().lower()
                    if any(w in text for w in ["precio", "gasolina", "combustible", "diesel"]):
                        full_url = href if href.startswith("http") else f"https://www.metroecuador.com.ec{href}"
                        result = _scrape_news_site(full_url, "MetroEcuador-article")
                        if len(result) >= 2:
                            return result
            except Exception:
                continue
    except Exception as e:
        logger.warning("Error en Metro Ecuador: %s", e)
    return {}


def fetch_latest_prices() -> dict:
    """Obtiene los precios mas recientes de combustibles en Ecuador.

    Intenta en orden: Petroecuador -> Metro Ecuador -> Expreso.ec
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

    # 1. EP Petroecuador
    prices = _scrape_petroecuador()
    if len(prices) >= 3:
        result["prices"] = prices
        result["source"] = "EP Petroecuador"
        result["success"] = True
        result["message"] = f"Precios obtenidos de EP Petroecuador: {len(prices)} combustibles"
        logger.info("Precios obtenidos de Petroecuador: %s", prices)
        return result

    # 2. Metro Ecuador
    prices_metro = _scrape_metro_ecuador()
    if len(prices_metro) >= 3:
        result["prices"] = prices_metro
        result["source"] = "Metro Ecuador"
        result["success"] = True
        result["message"] = f"Precios obtenidos de Metro Ecuador: {len(prices_metro)} combustibles"
        logger.info("Precios obtenidos de Metro Ecuador: %s", prices_metro)
        return result

    # Combinar lo que se tenga de ambas fuentes
    combined = {**prices, **prices_metro}
    if len(combined) >= 2:
        result["prices"] = combined
        result["source"] = "multiple"
        result["success"] = len(combined) >= 3
        result["message"] = f"Precios parciales obtenidos: {list(combined.keys())}"
        return result

    result["message"] = "No se pudieron obtener precios automaticamente. Registre manualmente."
    logger.warning("No se obtuvieron precios automaticamente")
    return result


def save_fetched_prices(prices: dict[str, float], price_date: date, db) -> dict:
    """Guarda los precios obtenidos en la BD y actualiza predicciones."""
    from app.database import crud
    from app.database.models import FuelPrice
    from app.database.connection import SessionLocal

    saved = []
    for fuel_type, new_price in prices.items():
        try:
            # Obtener precio anterior
            prev = db.query(FuelPrice).filter(
                FuelPrice.fuel_type == fuel_type,
                FuelPrice.date < price_date,
            ).order_by(FuelPrice.date.desc()).first()

            prev_price = float(prev.price) if prev else None
            change_pct = ((new_price - prev_price) / prev_price * 100) if prev_price else None

            # Determinar band_status
            band_status = "LIBRE"
            if fuel_type != "super_95" and prev_price:
                if change_pct >= 4.8:
                    band_status = "TECHO"
                elif change_pct <= -9.5:
                    band_status = "PISO"
                else:
                    band_status = "DENTRO"

            # Upsert
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
        from sqlalchemy import func
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
