/** Binding leído en runtime, no durante build ni en middleware. */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const MAX_BODY = 4 * 1024 * 1024;
const failure = (status: number, mensaje: string) => Response.json(
  { error_code: "API_NO_DISPONIBLE", mensaje }, { status, headers: { "Cache-Control": "no-store" } },
);

async function proxy(request: Request, { params }: { params: { path: string[] } }) {
  const base = process.env.APP_URL || (!process.env.VERCEL ? "http://127.0.0.1:8000" : "");
  if (!base) return failure(503, "El servicio API no está configurado.");
  if (!params.path.length || params.path.some((p) => !p || p === "." || p === ".." || /[/\\]/.test(p))) {
    return failure(400, "Ruta de API inválida.");
  }
  try {
    const url = new URL(`/api/v1/${params.path.map(encodeURIComponent).join("/")}`, base);
    url.search = new URL(request.url).search;
    const headers = new Headers();
    for (const name of ["authorization", "content-type", "accept", "idempotency-key", "x-correlation-id"]) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }
    let body: ArrayBuffer | undefined;
    if (!["GET", "HEAD"].includes(request.method) && request.body) {
      const reader = request.body.getReader();
      const chunks: Uint8Array[] = [];
      let total = 0;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > MAX_BODY) {
          await reader.cancel();
          return failure(413, "La solicitud supera el límite permitido.");
        }
        chunks.push(value);
      }
      body = new ArrayBuffer(total);
      const bytes = new Uint8Array(body);
      let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    }
    const upstream = await fetch(url, {
      method: request.method, headers, body, redirect: "manual", cache: "no-store", signal: request.signal,
    });
    if (upstream.status >= 300 && upstream.status < 400) {
      await upstream.body?.cancel();
      return failure(502, "La API devolvió una redirección inesperada.");
    }
    const outgoing = new Headers({ "Cache-Control": "private, no-store" });
    for (const name of ["content-type", "content-disposition", "vary", "x-content-type-options", "x-correlation-id"]) {
      const value = upstream.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: outgoing });
  } catch {
    return failure(503, "No se pudo conectar con la API.");
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS };
