import React, { useState, useRef } from "react";
import { Upload, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

export default function CargarExtraacto() {
  const { api } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // REGLA 1: Estado — SOLO primitivos, nunca objetos
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState("");
  const [totalMovimientos, setTotalMovimientos] = useState(0);
  const [causados, setCausados] = useState(0);
  const [pendientes, setPendientes] = useState(0);
  const [procesando, setProcesando] = useState(false);
  const [archivoNombre, setArchivoNombre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [banco, setBanco] = useState("bbva");
  const [fechaInicio, setFechaInicio] = useState("2026-01-01");
  const [fechaFin, setFechaFin] = useState("2026-01-31");

  const bancos = [
    { id: "bbva", nombre: "BBVA" },
    { id: "bancolombia", nombre: "Bancolombia" },
    { id: "davivienda", nombre: "Davivienda" },
    { id: "nequi", nombre: "Nequi" },
  ];

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.name.endsWith(".xlsx") || file.name.endsWith(".xls")) {
        setArchivo(file);
        setArchivoNombre(file.name);
        setError("");
        toast.success("Archivo seleccionado: " + file.name);
      } else {
        setError("Solo se aceptan archivos .xlsx o .xls");
        toast.error("Solo se aceptan archivos .xlsx o .xls");
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.name.endsWith(".xlsx") || file.name.endsWith(".xls")) {
        setArchivo(file);
        setArchivoNombre(file.name);
        setError("");
        toast.success("Archivo seleccionado: " + file.name);
      } else {
        setError("Solo se aceptan archivos .xlsx o .xls");
        toast.error("Solo se aceptan archivos .xlsx o .xls");
      }
    }
  };

  const procesar = async () => {
    // Validaciones
    if (!archivo) {
      setError("Selecciona un archivo primero");
      toast.error("Selecciona un archivo primero");
      return;
    }

    // Limpiar estado previo
    setError("");
    setJobId("");
    setTotalMovimientos(0);
    setCausados(0);
    setPendientes(0);
    setProcesando(true);

    try {
      console.log("📤 Enviando extracto:", {
        banco,
        fechaInicio,
        fechaFin,
        archivo: archivoNombre,
      });

      // REGLA 5: Construir FormData correctamente
      const formData = new FormData();
      formData.append("archivo", archivo);
      formData.append("banco", banco);
      formData.append("fecha", fechaFin);

      const response = await api.post(
        "/conciliacion/cargar-extracto",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        }
      );

      console.log("✅ Respuesta recibida:", response.data);

      // REGLA 3: Extraer campo por campo como primitivos (NUNCA objetos)
      const data = response.data;
      setJobId(String(data.job_id || ""));
      setTotalMovimientos(Number(data.total_movimientos) || 0);
      setCausados(Number(data.causados) || 0);
      setPendientes(Number(data.pendientes) || 0);
      setError("");
      setProcesando(false);

      toast.success("Extracto procesado correctamente");
    } catch (err: any) {
      console.error("❌ Error al procesar extracto:", err);

      // REGLA 2: Extraer el string antes de guardar en estado
      let errorString = "Error desconocido";

      // Intentar extraer el mensaje de error en orden de prioridad
      const detail = err?.response?.data?.detail;
      const msg = err?.response?.data?.message;
      const fallback = err?.message;

      if (typeof detail === "string" && detail.trim()) {
        errorString = detail;
      } else if (typeof msg === "string" && msg.trim()) {
        errorString = msg;
      } else if (typeof fallback === "string" && fallback.trim()) {
        errorString = fallback;
      } else {
        // Si nada de lo anterior funciona, intentar stringify como último recurso
        try {
          errorString = JSON.stringify(err?.response?.data || err);
        } catch {
          errorString = "Error procesando el extracto";
        }
      }

      setError(errorString);
      setJobId("");
      setTotalMovimientos(0);
      setCausados(0);
      setPendientes(0);
      setProcesando(false);

      toast.error(errorString);
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
          Procesa extractos bancarios automáticamente. El sistema clasificará los
          movimientos y creará journals en Alegra.
        </p>
      </div>

      {/* Formulario */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
        {/* Selector de banco */}
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-2">
            Banco *
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {bancos.map((b) => (
              <button
                key={b.id}
                onClick={() => setBanco(b.id)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  banco === b.id
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {b.nombre}
              </button>
            ))}
          </div>
        </div>

        {/* Fechas */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              Fecha inicio *
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
              Fecha fin *
            </label>
            <input
              type="date"
              value={fechaFin}
              onChange={(e) => setFechaFin(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Drag and drop */}
        <div
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            archivoNombre
              ? "border-green-400 bg-green-50"
              : "border-slate-300 hover:border-blue-400"
          }`}
        >
          <Upload size={40} className="mx-auto mb-3 text-slate-400" />
          <p className="text-sm text-slate-600 mb-2">
            Arrastra el extracto bancario aquí o{" "}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-blue-600 font-semibold hover:underline"
            >
              haz clic
            </button>
          </p>
          <p className="text-xs text-slate-500">
            Formatos aceptados: .xlsx, .xls
          </p>
          {archivoNombre && (
            <p className="text-sm text-green-600 font-medium mt-2">
              ✓ {archivoNombre}
            </p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFileSelect}
            className="hidden"
          />
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

      {/* REGLA 4: JSX — solo renderizar primitivos, nunca objetos */}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertCircle size={24} className="text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-bold text-red-900">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Resultados */}
      {(jobId || totalMovimientos > 0) && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6 space-y-4">
          <div className="flex items-start gap-3">
            <CheckCircle
              size={24}
              className="text-green-600 flex-shrink-0 mt-0.5"
            />
            <div className="flex-1">
              <h3 className="font-bold text-green-900 text-lg">
                Extracto procesado correctamente
              </h3>
              {jobId && (
                <p className="text-sm text-green-700 mt-1">Job ID: {jobId}</p>
              )}
            </div>
          </div>

          {/* Estadísticas */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-lg p-4">
              <p className="text-2xl font-bold text-slate-900">
                {totalMovimientos}
              </p>
              <p className="text-xs text-slate-600 uppercase tracking-wide">
                Movimientos detectados
              </p>
            </div>
            <div className="bg-white rounded-lg p-4">
              <p className="text-2xl font-bold text-green-600">{causados}</p>
              <p className="text-xs text-slate-600 uppercase tracking-wide">
                Causados automáticamente
              </p>
            </div>
            <div className="bg-white rounded-lg p-4">
              <p className="text-2xl font-bold text-amber-600">{pendientes}</p>
              <p className="text-xs text-slate-600 uppercase tracking-wide">
                Pendientes de revisión
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
