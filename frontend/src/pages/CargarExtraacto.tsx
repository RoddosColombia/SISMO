import React, { useState } from "react";
import { Upload, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

export default function CargarExtraacto() {
  const { api } = useAuth();

  // Estado mínimo — solo primitivos y File
  const [banco, setBanco] = useState("bbva");
  const [fechaInicio, setFechaInicio] = useState(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
      .toISOString()
      .split("T")[0]
  );
  const [fechaFin, setFechaFin] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [archivo, setArchivo] = useState<File | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [respuesta, setRespuesta] = useState(""); // SIEMPRE string
  const [error, setError] = useState(""); // SIEMPRE string

  const procesar = async () => {
    if (!archivo) {
      setError("Selecciona un archivo primero");
      return;
    }

    setProcesando(true);
    setError("");
    setRespuesta("");

    try {
      // Construir FormData
      const formData = new FormData();
      formData.append("archivo", archivo);
      formData.append("banco", banco);
      formData.append("fecha", fechaFin);

      console.log("📤 Enviando extracto:", {
        banco,
        fechaInicio,
        fechaFin,
        archivo: archivo.name,
      });

      // POST a backend
      const res = await api.post("/conciliacion/cargar-extracto", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      console.log("✅ Respuesta recibida:", res.data);

      // Guardar SIEMPRE como string (JSON.stringify)
      setRespuesta(JSON.stringify(res.data, null, 2));
      toast.success("Extracto procesado correctamente");
    } catch (err: any) {
      console.error("❌ Error al procesar extracto:", err);

      // Extraer mensaje de error como string
      let errorMsg = "Error procesando el extracto";
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        errorMsg = typeof detail === "string" ? detail : JSON.stringify(detail);
      } else if (err.message) {
        errorMsg = err.message;
      }

      // Guardar SIEMPRE como string
      setError(String(errorMsg));
      toast.error(String(errorMsg));
    } finally {
      setProcesando(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">
          Cargar Extracto Bancario
        </h2>
        <p className="text-slate-500 text-sm mt-1">
          Procesa extractos bancarios. Retorna JSON con resultados del procesamiento.
        </p>
      </div>

      {/* Formulario */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        {/* Selector de banco */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Banco
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {["bbva", "bancolombia", "davivienda", "nequi"].map((b) => (
              <button
                key={b}
                onClick={() => setBanco(b)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  banco === b
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {b.charAt(0).toUpperCase() + b.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Fechas */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              Fecha inicio
            </label>
            <input
              type="date"
              value={fechaInicio}
              onChange={(e) => setFechaInicio(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              Fecha fin
            </label>
            <input
              type="date"
              value={fechaFin}
              onChange={(e) => setFechaFin(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Archivo */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Archivo .xlsx o .xls
          </label>
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                setArchivo(e.target.files[0]);
                setError("");
              }
            }}
            className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          {archivo && (
            <p className="text-sm text-green-600 mt-2">✓ {archivo.name}</p>
          )}
        </div>

        {/* Botón procesar */}
        <Button
          onClick={procesar}
          disabled={!archivo || procesando}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
        >
          {procesando ? (
            <>
              <Loader2 size={16} className="mr-2 animate-spin" />
              Procesando...
            </>
          ) : (
            <>
              <Upload size={16} className="mr-2" />
              Procesar Extracto
            </>
          )}
        </Button>
      </div>

      {/* Error — string simple */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-sm text-red-700 font-semibold">Error:</p>
          <p className="text-sm text-red-600 mt-1">{error}</p>
        </div>
      )}

      {/* Respuesta — string simple en <pre> */}
      {respuesta && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <p className="text-sm text-green-700 font-semibold mb-2">
            Respuesta del servidor:
          </p>
          <pre className="text-xs text-green-600 bg-white p-3 rounded border border-green-100 overflow-auto max-h-96 font-mono">
            {respuesta}
          </pre>
        </div>
      )}
    </div>
  );
}
