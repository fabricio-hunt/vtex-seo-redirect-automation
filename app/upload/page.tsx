"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { DEFAULT_CONFIG, MIN_MATCH_SCORE } from "@/lib/types";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [xmlUrl, setXmlUrl] = useState(DEFAULT_CONFIG.xml_url);
  const [threshold, setThreshold] = useState(DEFAULT_CONFIG.threshold);
  const [checkHttpStatus, setCheckHttpStatus] = useState(DEFAULT_CONFIG.check_http_status);
  const [maxWorkers, setMaxWorkers] = useState(DEFAULT_CONFIG.max_workers);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Selecione uma planilha (.csv ou .xlsx) com a coluna URL.");
      return;
    }

    setSubmitting(true);
    setError(null);

    const form = new FormData();
    form.set("file", file);
    form.set("xml_url", xmlUrl);
    form.set("threshold", String(threshold));
    form.set("check_http_status", String(checkHttpStatus));
    form.set("max_workers", String(maxWorkers));

    try {
      const response = await fetch("/backend/jobs", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error ?? "Falha ao iniciar a execução.");
        return;
      }
      router.push(`/jobs/${data.id}`);
    } catch {
      setError("Falha de rede ao enviar a planilha.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <h1>Nova execução</h1>
      <p className="subtitle">
        Envie a planilha de URLs 404 (exportada do Google Search Console) com uma coluna <code>URL</code>.
      </p>

      {error && <div className="error-box">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="file">Planilha (.csv ou .xlsx)</label>
          <input
            id="file"
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="xml-url">URL do feed XML (Google Shopping)</label>
          <input id="xml-url" type="text" value={xmlUrl} onChange={(e) => setXmlUrl(e.target.value)} />
        </div>

        <div className="field">
          <label htmlFor="threshold">Limiar de similaridade para fuzzy match ({MIN_MATCH_SCORE}-100)</label>
          <input
            id="threshold"
            type="number"
            min={MIN_MATCH_SCORE}
            max={100}
            value={threshold}
            onChange={(e) => setThreshold(Math.max(MIN_MATCH_SCORE, Number(e.target.value)))}
          />
          <p className="hint">
            Por precisão, nenhuma URL entra no diagnóstico final com menos de {MIN_MATCH_SCORE}% de similaridade,
            mesmo que um valor menor seja informado aqui.
          </p>
        </div>

        <div className="field">
          <label htmlFor="max-workers">Threads para verificação HTTP</label>
          <input
            id="max-workers"
            type="number"
            min={1}
            max={30}
            value={maxWorkers}
            onChange={(e) => setMaxWorkers(Number(e.target.value))}
          />
        </div>

        <div className="field checkbox-row">
          <input
            id="check-http"
            type="checkbox"
            checked={checkHttpStatus}
            onChange={(e) => setCheckHttpStatus(e.target.checked)}
          />
          <label htmlFor="check-http">Verificar HTTP 200 dos destinos antes de incluir no CSV final</label>
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? "Enviando..." : "Iniciar recuperação"}
        </button>
      </form>
    </div>
  );
}
