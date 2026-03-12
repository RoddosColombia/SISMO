import React, { useState, useEffect, useCallback } from "react";
import { AlertTriangle, Calendar, Receipt, X, Loader2, ArrowRight, CheckCircle2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { formatCOP } from "../utils/formatters";

const SEVERITY_STYLES = {
  critical: { bg: "bg-red-50 border-red-300", badge: "bg-red-500 text-white", icon: <AlertTriangle size={16} className="text-red-500 flex-shrink-0 mt-0.5" /> },
  high: { bg: "bg-amber-50 border-amber-300", badge: "bg-amber-500 text-white", icon: <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" /> },
  medium: { bg: "bg-blue-50 border-blue-200", badge: "bg-blue-500 text-white", icon: <Calendar size={16} className="text-blue-500 flex-shrink-0 mt-0.5" /> },
  low: { bg: "bg-slate-50 border-slate-200", badge: "bg-slate-400 text-white", icon: <Receipt size={16} className="text-slate-400 flex-shrink-0 mt-0.5" /> },
};

export default function ProactiveAlerts() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("dismissed_alerts") || "[]"); } catch { return []; }
  });
  const [executing, setExecuting] = useState(null);
  const [done, setDone] = useState([]);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/dashboard/alerts");
      setAlerts(res.data || []);
    } catch {
      // Silently fail — alerts are non-critical
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  const dismiss = (id) => {
    const updated = [...dismissed, id];
    setDismissed(updated);
    sessionStorage.setItem("dismissed_alerts", JSON.stringify(updated));
  };

  const handleExecute = async (alert) => {
    if (alert.action_type === "navigate") {
      navigate(alert.action_payload.route);
      return;
    }
    setExecuting(alert.id);
    try {
      const res = await api.post("/dashboard/alerts/execute", {
        alert_type: alert.type,
        payload: alert.data,
      });
      toast.success(res.data.message);
      setDone(d => [...d, alert.id]);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error ejecutando acción");
    } finally {
      setExecuting(null);
    }
  };

  const visible = alerts.filter(a => !dismissed.includes(a.id) && !done.includes(a.id));

  if (loading) return (
    <div className="flex items-center gap-2 text-sm text-slate-400 py-2">
      <Loader2 size={14} className="animate-spin" /> Verificando estado contable...
    </div>
  );

  if (visible.length === 0) return null;

  return (
    <div className="space-y-2" data-testid="proactive-alerts-container">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Alertas del Agente IA</span>
        <span className="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full font-bold">{visible.length}</span>
      </div>
      {visible.map((alert) => {
        const style = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.low;
        return (
          <div
            key={alert.id}
            className={`flex items-start gap-3 p-3.5 rounded-xl border-2 ${style.bg} transition`}
            data-testid={`alert-${alert.id}`}
          >
            {style.icon}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-slate-800 leading-tight">
                {alert.title}
              </p>
              <p className="text-xs text-slate-600 mt-0.5">{alert.message}</p>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
              <button
                onClick={() => handleExecute(alert)}
                disabled={executing === alert.id}
                className="flex items-center gap-1 text-[11px] bg-[#0F2A5C] text-white px-3 py-1.5 rounded-lg hover:bg-[#163A7A] transition disabled:opacity-60 font-semibold whitespace-nowrap"
                data-testid={`alert-action-${alert.id}`}
              >
                {executing === alert.id ? (
                  <Loader2 size={11} className="animate-spin" />
                ) : (
                  <ArrowRight size={11} />
                )}
                {alert.action_label}
              </button>
              <button onClick={() => dismiss(alert.id)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-white/60 transition"
                data-testid={`alert-dismiss-${alert.id}`}>
                <X size={13} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
