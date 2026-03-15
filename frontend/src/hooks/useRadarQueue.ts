import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import type { RadarItem } from "../components/shared/RadarCard";

export function useRadarQueue(pollIntervalMs = 60_000) {
  const { api } = useAuth();
  const [queue, setQueue]     = useState<RadarItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await api.get<RadarItem[]>("/radar/queue");
      setQueue(res.data);
    } catch {
      // fail silently
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchQueue();
    const id = setInterval(fetchQueue, pollIntervalMs);
    return () => clearInterval(id);
  }, [fetchQueue, pollIntervalMs]);

  return { queue, loading, refetch: fetchQueue };
}
