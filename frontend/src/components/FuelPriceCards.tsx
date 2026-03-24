'use client';

import { TrendingUp, TrendingDown, Minus, Fuel } from 'lucide-react';

interface FuelPriceCardsProps {
  prices: FuelPrice[];
}

const fuelConfig: Record<string, { label: string; gradient: string; color: string }> = {
  extra: { label: 'Extra', gradient: 'fuel-extra', color: '#14b8a6' },
  ecopais: { label: 'EcoPais', gradient: 'fuel-ecopais', color: '#84cc16' },
  super_95: { label: 'Super 95', gradient: 'fuel-super', color: '#f59e0b' },
  diesel: { label: 'Diesel', gradient: 'fuel-diesel', color: '#ef4444' },
};

export default function FuelPriceCards({ prices }: FuelPriceCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {prices.map((fuel) => {
        const config = fuelConfig[fuel.type] || fuelConfig.extra;
        const isUp = fuel.change_direction === 'SUBE';
        const isDown = fuel.change_direction === 'BAJA';
        const isEqual = fuel.change_direction === 'IGUAL';

        return (
          <div
            key={fuel.type}
            className={`${config.gradient} rounded-xl border p-5 shadow-lg`}
          >
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2">
                <Fuel className="w-5 h-5 text-white/70" />
                <h3 className="text-sm font-medium text-white/80 uppercase tracking-wider">
                  {config.label}
                </h3>
              </div>
              <span
                className={
                  fuel.band_applied === 'LIBRE' ? 'badge-libre' : 'badge-band'
                }
              >
                {fuel.band_applied === 'LIBRE' ? 'Libre' : `Banda: ${fuel.band_applied}`}
              </span>
            </div>

            <div className="flex items-end gap-2 mb-3">
              <span className="text-3xl font-bold text-white">
                ${fuel.price_per_gallon.toFixed(2)}
              </span>
              <span className="text-sm text-white/60 mb-1">/galon</span>
            </div>

            <div className="flex items-center gap-2">
              {isUp && <TrendingUp className="w-4 h-4 text-red-300" />}
              {isDown && <TrendingDown className="w-4 h-4 text-emerald-300" />}
              {isEqual && <Minus className="w-4 h-4 text-white/50" />}
              <span
                className={
                  isUp
                    ? 'badge-down'
                    : isDown
                    ? 'badge-up'
                    : 'badge-neutral'
                }
              >
                {isUp ? '+' : isDown ? '' : ''}
                {fuel.change_percent.toFixed(2)}% vs mes anterior
              </span>
            </div>

            {fuel.effective_date && (
              <p className="text-xs text-white/40 mt-2">
                Vigente desde: {fuel.effective_date}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
