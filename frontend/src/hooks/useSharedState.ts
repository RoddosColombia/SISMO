import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

export interface PortfolioHealth {
  activos: number;
  en_mora: number;
  tasa_mora: number;
  cartera_activa: number;
  total_cobrado: number;
}

export function useSharedState(pollIntervalMs = 30_000) {
  const { api } = useAuth();
  const [data, setData]       = useState<PortfolioHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get<PortfolioHealth>("/radar/portfolio-health");
      setData(res.data);
      setLastUpdated(new Date());
    } catch {
      // fail silently — stale data is fine
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, pollIntervalMs);
    return () => clearInterval(id);
  }, [fetchData, pollIntervalMs]);

  return { data, loading, lastUpdated, refetch: fetchData };
}
