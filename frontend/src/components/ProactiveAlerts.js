import React, { useState, useEffect, useCallback } from "react";
import { AlertTriangle, Calendar, Receipt, X, Loader2, ArrowRight } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const SEV = {
  critical: { border: "#FF4444", iconColor: "#FF4444", icon: AlertTriangle },
  high:     { border: "#FFB300", iconColor: "#FFB300", icon: AlertTriangle },
  medium:   { border: "#00E5FF", iconColor: "#00E5FF", icon: Calendar },
  low:      { border: "#444",    iconColor: "#555",    icon: Receipt },
};

export default function ProactiveAlerts() {
  const { api } = useAuth();
  const navigate = useNavigate();
  const [alerts, setAlerts]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("dismissed_alerts") || "[]"); } catch { return []; }
  });
  const [executing, setExecuting] = useState(null);
  const [done, setDone]           = useState([]);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/dashboard/alerts");
      setAlerts(res.data || []);
    } catch { /* non-critical */ } finally {
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
    if (alert.action_type === "navigate") { navigate(alert.action_payload.route); return; }
    setExecuting(alert.id);
    try {
      const res = await api.post("/dashboard/alerts/execute", { alert_type: alert.type, payload: alert.data });
      toast.success(res.data.message);
      setDone(d => [...d, alert.id]);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Error ejecutando acción");
    } finally { setExecuting(null); }
  };

  const visible = alerts.filter(a => !dismissed.includes(a.id) && !done.includes(a.id));

  if (loading) return (
    <div className="flex items-center gap-2 text-xs py-2" style={{ color: "#555" }}>
      <Loader2 size={13} className="animate-spin" style={{ color: "#00E5FF" }} /> Verificando estado contable...
    </div>
  );
  if (visible.length === 0) return null;

  return (
    <div className="space-y-2" data-testid="proactive-alerts-container">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#555" }}>Alertas del Agente IA</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
          style={{ background: "#FF444420", color: "#FF4444", border: "1px solid #FF444440" }}>
          {visible.length}
        </span>
      </div>
      {visible.map((alert) => {
        const sev = SEV[alert.severity] || SEV.low;
        const Icon = sev.icon;
        return (
          <div key={alert.id}
            className="flex items-start gap-3 p-3.5 rounded-xl transition"
            style={{ background: "#1A1A1A", border: `1px solid ${sev.border}40`, borderLeft: `3px solid ${sev.border}` }}
            data-testid={`alert-${alert.id}`}
          >
            <Icon size={15} className="flex-shrink-0 mt-0.5" style={{ color: sev.iconColor }} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-white leading-tight">{alert.title}</p>
              <p className="text-xs mt-0.5" style={{ color: "#888" }}>{alert.message}</p>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
              <button onClick={() => handleExecute(alert)} disabled={executing === alert.id}
                className="flex items-center gap-1 text-[11px] font-bold px-3 py-1.5 rounded-lg transition disabled:opacity-50 whitespace-nowrap"
                style={{ background: "#00E5FF15", border: "1px solid #00E5FF50", color: "#00E5FF" }}
                data-testid={`alert-action-${alert.id}`}>
                {executing === alert.id ? <Loader2 size={11} className="animate-spin" /> : <ArrowRight size={11} />}
                {alert.action_label}
              </button>
              <button onClick={() => dismiss(alert.id)}
                className="p-1.5 rounded-lg transition"
                style={{ color: "#444" }}
                onMouseEnter={e => e.currentTarget.style.color = "#888"}
                onMouseLeave={e => e.currentTarget.style.color = "#444"}
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
