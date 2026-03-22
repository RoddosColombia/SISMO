import React, { useState, useRef } from "react";
import { Upload, Loader2, CheckCircle, AlertCircle, X } from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../contexts/AuthContext";
import { toast } from "sonner";

interface ProcesosResult {
  status: "processing" | "success" | "error";
  job_id: string;
  total_movimientos: number;
  causados: number;
  pendientes: number;
  error?: string;
  movimientos_pendientes?: Array<{
    fecha: string;
    descripcion: string;
    monto: number;
    sugerencia_cuenta: string;
    confianza: number;
  }>;
}

export default function CargarExtraacto() {
  const { api, user } = useAuth();
  const [banco, setBanco] = useState("bbva");
  const today = new Date().toISOString().split("T")[0];
  const [fechaInicio, setFechaInicio] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split("T")[0]);
  const [fechaFin, setFechaFin] = useState(today);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [cargando, setCargando] = useState(false);
  const [resultado, setResultado] = useState<ProcesosResult | null>(null);
  const [componentError, setComponentError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        toast.success("Archivo seleccionado: " + file.name);
      } else {
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
        toast.success("Archivo seleccionado: " + file.name);
      } else {
        toast.error("Solo se aceptan archivos .xlsx o .xls");
      }
    }
  };

  const procesar = async () => {
    if (!archivo) {
      toast.error("Selecciona un archivo primero");
      return;
    }

    setCargando(true);
    setComponentError(null);
    try {
      const formData = new FormData();
      formData.append("archivo", archivo);
      formData.append("banco", banco);
      formData.append("fecha", fechaFin);

      console.log("📤 Enviando extracto:", { banco, fechaInicio, fechaFin, archivo: archivo.name });
      const res = await api.post("/conciliacion/cargar-extracto", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      console.log("✅ Respuesta recibida:", res.data);
      const data = res.data;

      const resultado_data: ProcesosResult = {
        status: (data.status === "procesando" || data.status === "processing") ? "processing" : "success",
        job_id: data.job_id || "",
        total_movimientos: parseInt(data.total_movimientos) || 0,
        causados: parseInt(data.causados) || 0,
        pendientes: parseInt(data.pendientes) || 0,
        movimientos_pendientes: Array.isArray(data.movimientos_pendientes) ? data.movimientos_pendientes : [],
      };

      setResultado(resultado_data);
      toast.success("Extracto procesado correctamente");
    } catch (error: any) {
      console.error("❌ Error al procesar extracto:", error);
      const errorMsg = error.response?.data?.detail || error.message || "Error procesando el extracto";
      setComponentError(errorMsg);
      setResultado({
        status: "error",
        job_id: "",
        total_movimientos: 0,
        causados: 0,
        pendientes: 0,
        error: errorMsg,
      });
      toast.error(errorMsg);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      {/* Error boundary display */}
      {componentError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertCircle size={24} className="text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-bold text-red-900">Error del componente</h3>
              <p className="text-sm text-red-700 mt-1">{componentError}</p>
              <p className="text-xs text-red-600 mt-2">Revisa la consola del navegador (F12) para más detalles.</p>
            </div>
            <button
              onClick={() => setComponentError(null)}
              className="text-red-600 hover:text-red-700"
            >
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      <div>
        <h2 className="text-2xl font-bold text-slate-900">Cargar Extracto Bancario</h2>
        <p className="text-slate-500 text-sm mt-1">
          Procesa extractos bancarios automáticamente. El sistema clasificará los movimientos y creará journals en Alegra.
        </p>
      </div>

      {/* Formulario de carga */}
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

        {/* Date range picker */}
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
            archivo
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
          <p className="text-xs text-slate-500">Formatos aceptados: .xlsx, .xls</p>
          {archivo && (
            <p className="text-sm text-green-600 font-medium mt-2">
              ✓ {archivo.name}
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
          disabled={!archivo || cargando}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
        >
          {cargando ? (
            <>
              <Loader2 size={16} className="mr-2 animate-spin" />
              Procesando...
            </>
          ) : (
            "Procesar Extracto"
          )}
        </Button>
      </div>

      {/* Resultado */}
      {resultado && (
        <div className={`rounded-xl border p-6 ${
          resultado.status === "success" ? "bg-green-50 border-green-200" :
          resultado.status === "error" ? "bg-red-50 border-red-200" :
          "bg-blue-50 border-blue-200"
        }`}>
          {/* Safety: fallback if resultado is malformed */}
          {typeof resultado.status !== "string" && (
            <div className="text-red-600 text-sm mb-4">Respuesta malformada del servidor</div>
          )}
          <div className="flex items-start gap-3 mb-4">
            {resultado.status === "success" && (
              <CheckCircle size={24} className="text-green-600 flex-shrink-0 mt-1" />
            )}
            {resultado.status === "error" && (
              <AlertCircle size={24} className="text-red-600 flex-shrink-0 mt-1" />
            )}
            {resultado.status === "processing" && (
              <Loader2 size={24} className="text-blue-600 flex-shrink-0 mt-1 animate-spin" />
            )}
            <div className="flex-1">
              <h3 className="font-bold text-lg">
                {resultado.status === "success" && "Extracto procesado correctamente"}
                {resultado.status === "error" && "Error al procesar el extracto"}
                {resultado.status === "processing" && "Procesando..."}
              </h3>
              {resultado.error && (
                <p className="text-sm text-red-700 mt-1">{resultado.error}</p>
              )}
            </div>
          </div>

          {resultado.status !== "error" && (
            <>
              {/* Estadísticas */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className="bg-white rounded-lg p-4">
                  <p className="text-2xl font-bold text-slate-900">
                    {resultado.total_movimientos}
                  </p>
                  <p className="text-xs text-slate-600 uppercase tracking-wide">
                    Movimientos detectados
                  </p>
                </div>
                <div className="bg-white rounded-lg p-4">
                  <p className="text-2xl font-bold text-green-600">
                    {resultado.causados}
                  </p>
                  <p className="text-xs text-slate-600 uppercase tracking-wide">
                    Causados automáticamente
                  </p>
                </div>
                <div className="bg-white rounded-lg p-4">
                  <p className="text-2xl font-bold text-amber-600">
                    {resultado.pendientes}
                  </p>
                  <p className="text-xs text-slate-600 uppercase tracking-wide">
                    Pendientes de revisión
                  </p>
                </div>
              </div>

              {/* Tabla de pendientes */}
              {resultado.movimientos_pendientes && resultado.movimientos_pendientes.length > 0 && (
                <div>
                  <h4 className="font-bold text-slate-900 mb-3">
                    Movimientos pendientes de clasificación
                  </h4>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {resultado.movimientos_pendientes.map((mov, i) => {
                      try {
                        const monto = typeof mov.monto === "number" ? mov.monto : parseInt(mov.monto) || 0;
                        const confianza = typeof mov.confianza === "number" ? mov.confianza : parseFloat(mov.confianza) || 0;
                        return (
                          <div key={i} className="bg-white rounded-lg p-3 border border-slate-200">
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
                              <div>
                                <p className="text-xs text-slate-600 font-medium">Fecha</p>
                                <p className="font-medium">{mov.fecha || "—"}</p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-600 font-medium">Descripción</p>
                                <p className="font-medium truncate">{mov.descripcion || "—"}</p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-600 font-medium">Monto</p>
                                <p className="font-medium">
                                  ${monto.toLocaleString("es-CO")}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-600 font-medium">Sugerencia</p>
                                <p className="text-xs font-medium truncate">
                                  {mov.sugerencia_cuenta || "—"}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-600 font-medium">Confianza</p>
                                <p className={`font-bold ${
                                  confianza >= 70 ? "text-green-600" : "text-amber-600"
                                }`}>
                                  {Math.round(confianza)}%
                                </p>
                              </div>
                            </div>
                          </div>
                        );
                      } catch (err) {
                        console.error("Error rendering movimiento:", err, mov);
                        return (
                          <div key={i} className="bg-red-50 rounded-lg p-3 border border-red-200 text-sm text-red-600">
                            Error mostrando movimiento {i + 1}
                          </div>
                        );
                      }
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
