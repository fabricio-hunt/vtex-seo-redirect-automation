"use client";

import { use, useEffect, useRef, useState } from "react";
import type { JobDetailResponse } from "@/lib/types";

const PHASE_LABELS: Record<string, string> = {
  matching: "Comparando com o feed",
  http_check: "Verificando status HTTP",
  done: "Concluído",
};

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<JobDetailResponse | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    stoppedRef.current = false;

    async function fetchDetail() {
      const response = await fetch(`/backend/jobs/${id}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Falha ao carregar o job.");
      return data as JobDetailResponse;
    }

    async function advanceOnce() {
      const response = await fetch(`/backend/jobs/${id}/advance`, { method: "POST" });
      const data = await response.json();
      if (!response.ok && response.status !== 500) throw new Error(data.error ?? "Falha ao processar.");
      return data as { status: string; error?: string };
    }

    async function loop() {
      try {
        const initial = await fetchDetail();
        if (stoppedRef.current) return;
        setJob(initial);
        if (initial.status !== "running") return;

        while (!stoppedRef.current) {
          const result = await advanceOnce();
          if (stoppedRef.current) return;

          const detail = await fetchDetail();
          if (stoppedRef.current) return;
          setJob(detail);

          if (result.status !== "running") return;
          await new Promise((resolve) => setTimeout(resolve, 600));
        }
      } catch (err) {
        if (!stoppedRef.current) {
          setFetchError(err instanceof Error ? err.message : "Erro inesperado.");
        }
      }
    }

    loop();
    return () => {
      stoppedRef.current = true;
    };
  }, [id]);

  if (fetchError) {
    return <div className="error-box">{fetchError}</div>;
  }

  if (!job) {
    return <div className="empty-state">Carregando...</div>;
  }

  const { progress } = job;
  const badgeClass = job.status === "done" ? "done" : job.status === "error" ? "error" : "";

  return (
    <div className="card">
      <h1>{job.filename}</h1>
      <p className="subtitle">
        Iniciado em {new Date(job.createdAt).toLocaleString("pt-BR")} · <span className={`phase-badge ${badgeClass}`}>{job.status === "error" ? "Erro" : PHASE_LABELS[progress.phase]}</span>
      </p>

      {job.status === "error" && <div className="error-box">{job.error}</div>}

      {job.status !== "error" && (
        <>
          <div className="field">
            <div className="progress-label">
              Comparando URLs: {progress.rows_matched} / {progress.rows_total}
            </div>
            <ProgressBar current={progress.rows_matched} total={progress.rows_total} />
          </div>

          {job.config.check_http_status && (
            <div className="field">
              <div className="progress-label">
                Verificando HTTP: {progress.urls_checked} / {progress.urls_total}
              </div>
              <ProgressBar current={progress.urls_checked} total={progress.urls_total} />
            </div>
          )}
        </>
      )}

      {Object.keys(progress.match_type_breakdown).length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h2>Resultado por tipo de match</h2>
          <table>
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Quantidade</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(progress.match_type_breakdown).map(([type, count]) => (
                <tr key={type}>
                  <td>{type}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {job.status === "done" && job.stats && job.resultUrls && (
        <>
          <div className="stat-grid">
            <div className="stat-tile">
              <div className="value">{job.stats.rows_total}</div>
              <div className="label">URLs 404 processadas</div>
            </div>
            <div className="stat-tile">
              <div className="value">{job.stats.valid_redirects}</div>
              <div className="label">Redirects válidos</div>
            </div>
          </div>
          <div className="download-row">
            <a href={`/backend/jobs/${job.id}/download/redirects`}>
              <button type="button">Baixar redirects.csv</button>
            </a>
            <a href={`/backend/jobs/${job.id}/download/review`}>
              <button type="button" className="secondary">
                Baixar review.csv
              </button>
            </a>
          </div>
        </>
      )}
    </div>
  );
}
