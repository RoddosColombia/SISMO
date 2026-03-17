/**
 * descargar.ts — Helper de descargas autenticadas (BUILD 21 — BUG 2 fix)
 *
 * Uso:
 *   await descargarArchivo(url, "archivo.xlsx", token);
 *   await descargarArchivo(url, "reporte.pdf", token);
 */

/**
 * Descarga un archivo desde una URL autenticada.
 * Muestra un mensaje de error claro en español si algo falla.
 */
export async function descargarArchivo(
  url: string,
  nombreArchivo: string,
  token: string | null | undefined,
  onError?: (msg: string) => void,
): Promise<boolean> {
  try {
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(url, { headers });

    if (!res.ok) {
      let detail = "";
      try {
        const body = await res.json();
        detail = body?.detail || body?.message || "";
      } catch {
        detail = await res.text().catch(() => "");
      }
      const msg = detail
        ? `Error ${res.status}: ${detail}`
        : `No se pudo descargar el archivo (HTTP ${res.status}). Verifica tu sesión e inténtalo de nuevo.`;
      onError?.(msg);
      return false;
    }

    const blob = await res.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = nombreArchivo;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(href);
    return true;
  } catch (e: any) {
    const msg = `No se pudo descargar: ${e?.message || "Error de red"}`;
    onError?.(msg);
    return false;
  }
}
