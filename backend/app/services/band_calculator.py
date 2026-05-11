"""Implementacion del sistema de bandas del Decreto 308 para combustibles en Ecuador.

El sistema de bandas asimetricas establece:
- Techo maximo: +5% mensual (el precio no puede subir mas del 5%)
- Piso minimo: -10% mensual (el precio no puede bajar mas del 10%)
- La Super 95 tiene precio libre (no aplica el sistema de bandas)
- Los precios se actualizan el dia 11 de cada mes
- Decreto Ejecutivo No. 308 (junio 2024) establece las bandas asimetricas

La formula de precio:
Precio final = Precio en Terminal (con IVA) + Margen de Comercializacion (con IVA)
Donde Precio en Terminal incluye: costos de importacion + transporte + almacenamiento
    + margen Petroecuador + costo de capital + IVA (15%)
"""

from datetime import date

from app.config import settings

# Fecha de referencia del modelo (jun-2023 = mes 0)
_MODEL_BASE_DATE = date(2023, 6, 1)

def _months_since_base(d: date = None) -> int:
    """Calcula meses transcurridos desde jun-2023."""
    if d is None:
        d = date.today()
    return (d.year - _MODEL_BASE_DATE.year) * 12 + (d.month - _MODEL_BASE_DATE.month)


class BandCalculator:
    """Implementa la logica del Decreto 308 - Sistema de bandas de precios."""

    def calculate_theoretical_price(self, wti_price: float, fuel_type: str) -> float:
        """Calcula el precio teorico basado en el WTI y la formula del gobierno.

        Para Extra, EcoPais y Diesel usa la formula del Decreto 308.
        Para Super 95 usa un modelo cuadratico calibrado con datos reales,
        ya que tiene precio libre y las comercializadoras lo fijan segun mercado.

        Args:
            wti_price: Precio del WTI en USD/barril.
            fuel_type: Tipo de combustible (extra, ecopais, super_95, diesel).

        Returns:
            Precio teorico en USD/galon.
        """
        # Super 95: modelo cuadratico (precio libre, no usa Decreto 308)
        if fuel_type == "super_95":
            return self._calculate_super95_price(wti_price)

        # Extra, EcoPais, Diesel: formula del Decreto 308
        return self._calculate_decree308_price(wti_price, fuel_type)

    def _calculate_super95_price(self, wti_price: float, target_month_offset: int = 1) -> float:
        """Modelo hibrido para Super 95 (precio libre).

        Regresion multiple calibrada con 34 meses reales (jun-2023 a abr-2026).
        Super = WTI_COEFF*WTI + TIME_COEFF*mes + INTERCEPT
        MAPE=3.6% (mejor que lineal simple MAPE=7%).
        target_month_offset: cuantos meses adelante se predice (1=proximo mes).
        """
        current_month = _months_since_base()
        target_month = current_month + target_month_offset
        price = (
            settings.SUPER_95_WTI_COEFF * wti_price
            + settings.SUPER_95_TIME_COEFF * target_month
            + settings.SUPER_95_INTERCEPT
        )
        return round(max(price, 1.50), 3)

    def _calculate_decree308_price(self, wti_price: float, fuel_type: str) -> float:
        """Formula del Decreto 308 para combustibles regulados."""
        # 1. Costo de importacion base: WTI ($/barril) -> $/galon
        import_cost_gallon = wti_price * settings.WTI_TO_GALLON_FACTOR * settings.IMPORT_COST_WEIGHT

        # 2. Ajuste por tipo de combustible (octanaje, refinacion)
        refining_factor = settings.FUEL_REFINING_FACTOR.get(fuel_type, 1.0)
        import_cost_adjusted = import_cost_gallon * refining_factor

        # 3. Costos fijos de la cadena
        transport = settings.TRANSPORT_COST
        storage = settings.STORAGE_COST
        petroecuador_margin = settings.PETROECUADOR_MARGIN

        # 4. Costo de capital
        subtotal_pre_capital = import_cost_adjusted + transport + storage + petroecuador_margin
        capital_cost = subtotal_pre_capital * settings.CAPITAL_COST_RATE

        # 5. Subtotal antes de IVA
        subtotal_before_iva = subtotal_pre_capital + capital_cost

        # 6. IVA sobre el precio en terminal
        iva_terminal = subtotal_before_iva * settings.IVA_RATE
        terminal_price_with_iva = subtotal_before_iva + iva_terminal

        # 7. Margen de comercializacion + su IVA
        commercial_margin = settings.COMMERCIAL_MARGIN
        commercial_margin_iva = commercial_margin * settings.IVA_RATE

        # 8. Precio final teorico
        theoretical_price = terminal_price_with_iva + commercial_margin + commercial_margin_iva

        return round(max(theoretical_price, 0.50), 3)

    def apply_band(self, current_price: float, theoretical_price: float, fuel_type: str) -> dict:
        """Aplica la banda de precios (+5% techo, -10% piso).

        Para combustibles con sistema de bandas, limita el cambio mensual.
        Para Super 95 (precio libre), no aplica limites.

        Args:
            current_price: Precio vigente actual (USD/galon).
            theoretical_price: Precio calculado por formula de costo.
            fuel_type: Tipo de combustible.

        Returns:
            Dict con precio resultante, estado de banda y limites.
        """
        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
        has_band = fuel_config.get("band_system", True)

        if not has_band:
            # Super 95: precio libre
            change_pct = ((theoretical_price - current_price) / current_price) * 100 if current_price > 0 else 0
            return {
                "result": round(theoretical_price, 3),
                "status": "LIBRE",
                "capped": False,
                "max_price": None,
                "min_price": None,
                "change_pct": round(change_pct, 2),
            }

        max_increase = fuel_config.get("max_increase", 0.05)
        max_decrease = fuel_config.get("max_decrease", -0.10)

        max_price = round(current_price * (1 + max_increase), 3)
        min_price = round(current_price * (1 + max_decrease), 3)

        if theoretical_price > max_price:
            result_price = max_price
            status = "TECHO"
            capped = True
        elif theoretical_price < min_price:
            result_price = min_price
            status = "PISO"
            capped = True
        else:
            result_price = round(theoretical_price, 3)
            status = "DENTRO"
            capped = False

        change_pct = ((result_price - current_price) / current_price) * 100 if current_price > 0 else 0

        return {
            "result": result_price,
            "status": status,
            "capped": capped,
            "max_price": max_price,
            "min_price": min_price,
            "change_pct": round(change_pct, 2),
        }

    def simulate(self, wti_price: float, current_price: float, fuel_type: str) -> dict:
        """Simulacion completa: WTI -> precio teorico -> banda -> resultado.

        Args:
            wti_price: Precio WTI en USD/barril.
            current_price: Precio actual del combustible en USD/galon.
            fuel_type: Tipo de combustible.

        Returns:
            Resultado completo de la simulacion con desglose de formula.
        """
        fuel_config = settings.FUEL_TYPES.get(fuel_type, {})
        fuel_name = fuel_config.get("name", fuel_type)

        # Calcular precio teorico
        theoretical = self.calculate_theoretical_price(wti_price, fuel_type)

        # Aplicar banda
        band_result = self.apply_band(current_price, theoretical, fuel_type)

        # Desglose de la formula
        breakdown = self.get_formula_breakdown(wti_price, fuel_type)

        diff_vs_current = band_result["result"] - current_price
        diff_pct = (diff_vs_current / current_price) * 100 if current_price > 0 else 0

        return {
            "fuel_type": fuel_type,
            "fuel_name": fuel_name,
            "current_price": current_price,
            "wti_input": wti_price,
            "theoretical_price": theoretical,
            "max_price": band_result["max_price"],
            "min_price": band_result["min_price"],
            "final_price": band_result["result"],
            "band_status": band_result["status"],
            "band_applied": band_result["capped"],
            "difference_vs_current": round(diff_vs_current, 3),
            "difference_pct": round(diff_pct, 2),
            "formula_breakdown": breakdown,
        }

    def get_formula_breakdown(self, wti_price: float, fuel_type: str) -> dict:
        """Devuelve el desglose de la formula paso a paso.

        Retorna cada componente para mostrar en la UI de forma educativa.

        Args:
            wti_price: Precio del WTI en USD/barril.
            fuel_type: Tipo de combustible.

        Returns:
            Dict con cada componente de la formula.
        """
        if fuel_type == "super_95":
            price = self._calculate_super95_price(wti_price)
            return {
                "wti_price_barrel": round(wti_price, 2),
                "modelo": "hibrido (WTI + tendencia temporal)",
                "descripcion": "Precio libre - regresion multiple calibrada con 34 meses de datos reales",
                "wti_coeff": settings.SUPER_95_WTI_COEFF,
                "time_coeff": settings.SUPER_95_TIME_COEFF,
                "intercept": settings.SUPER_95_INTERCEPT,
                "mape_historico": "3.6%",
                "theoretical_price": round(price, 4),
            }

        import_cost_gallon = wti_price * settings.WTI_TO_GALLON_FACTOR * settings.IMPORT_COST_WEIGHT
        refining_factor = settings.FUEL_REFINING_FACTOR.get(fuel_type, 1.0)
        refining_adjustment = import_cost_gallon * refining_factor
        transport = settings.TRANSPORT_COST
        storage = settings.STORAGE_COST
        petroecuador_margin = settings.PETROECUADOR_MARGIN

        subtotal_pre_capital = refining_adjustment + transport + storage + petroecuador_margin
        capital_cost = subtotal_pre_capital * settings.CAPITAL_COST_RATE
        subtotal_before_iva = subtotal_pre_capital + capital_cost

        iva_amount = subtotal_before_iva * settings.IVA_RATE
        terminal_price_with_iva = subtotal_before_iva + iva_amount

        commercial_margin = settings.COMMERCIAL_MARGIN
        commercial_margin_iva = commercial_margin * settings.IVA_RATE

        theoretical_price = terminal_price_with_iva + commercial_margin + commercial_margin_iva

        return {
            "wti_price_barrel": round(wti_price, 2),
            "import_cost_gallon": round(import_cost_gallon, 4),
            "refining_adjustment": round(refining_adjustment, 4),
            "transport_cost": round(transport, 4),
            "storage_cost": round(storage, 4),
            "petroecuador_margin": round(petroecuador_margin, 4),
            "capital_cost": round(capital_cost, 4),
            "subtotal_before_iva": round(subtotal_before_iva, 4),
            "iva_amount": round(iva_amount, 4),
            "terminal_price_with_iva": round(terminal_price_with_iva, 4),
            "commercial_margin": round(commercial_margin, 4),
            "commercial_margin_iva": round(commercial_margin_iva, 4),
            "theoretical_price": round(theoretical_price, 4),
        }

    @staticmethod
    def get_next_update_date() -> dict:
        """Retorna la fecha del proximo dia 11 y los dias restantes."""
        today = date.today()
        day_11 = settings.PRICE_UPDATE_DAY
        current_month_11 = date(today.year, today.month, day_11)

        if today <= current_month_11:
            next_update = current_month_11
        else:
            if today.month == 12:
                next_update = date(today.year + 1, 1, day_11)
            else:
                next_update = date(today.year, today.month + 1, day_11)

        days_remaining = (next_update - today).days

        return {
            "next_update_date": next_update.isoformat(),
            "days_remaining": days_remaining,
            "is_update_day": days_remaining == 0,
        }

    @staticmethod
    def analyze_band_history(historical_data: list, fuel_type: str = "extra") -> dict:
        """Calcula estadisticas del historial de aplicacion de bandas.

        Args:
            historical_data: Lista de dicts con date y precio del combustible.
            fuel_type: Tipo de combustible a analizar.

        Returns:
            Dict con registros detallados y estadisticas globales.
        """
        if len(historical_data) < 2:
            return {"records": [], "stats": {}}

        records = []
        increases = 0
        decreases = 0
        no_change = 0
        ceiling_hits = 0
        floor_hits = 0
        all_changes_pct = []

        for i in range(1, len(historical_data)):
            prev = historical_data[i - 1]
            curr = historical_data[i]

            prev_price = prev.get(fuel_type, 0)
            curr_price = curr.get(fuel_type, 0)

            if prev_price <= 0:
                continue

            change = curr_price - prev_price
            change_pct = (change / prev_price) * 100
            all_changes_pct.append(change_pct)

            max_price = round(prev_price * 1.05, 3)
            min_price = round(prev_price * 0.90, 3)

            tolerance = 0.005
            if curr_price >= max_price - tolerance:
                status = "TECHO"
                ceiling_hits += 1
            elif curr_price <= min_price + tolerance:
                status = "PISO"
                floor_hits += 1
            else:
                status = "DENTRO"

            if change > 0.001:
                increases += 1
            elif change < -0.001:
                decreases += 1
            else:
                no_change += 1

            records.append({
                "date": curr.get("date", ""),
                "fuel_type": fuel_type,
                "price": round(curr_price, 3),
                "previous_price": round(prev_price, 3),
                "change": round(change, 3),
                "change_pct": round(change_pct, 2),
                "band_status": status,
            })

        all_prices = [r["price"] for r in records if r["price"] > 0]
        avg_change = sum(all_changes_pct) / len(all_changes_pct) if all_changes_pct else 0

        stats = {
            "total_months": len(records),
            "increases": increases,
            "decreases": decreases,
            "no_change": no_change,
            "times_ceiling_hit": ceiling_hits,
            "times_floor_hit": floor_hits,
            "max_price": max(all_prices) if all_prices else 0,
            "min_price": min(all_prices) if all_prices else 0,
            "avg_monthly_change_pct": round(avg_change, 2),
        }

        return {"records": records, "stats": stats}
