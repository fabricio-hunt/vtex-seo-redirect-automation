"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { JobSummary } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  running: "Em andamento",
  done: "Concluído",
  error: "Erro",
};

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/backend/jobs", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setJobs(data.jobs))
      .catch(() => setError("Falha ao carregar o histórico."));
  }, []);

  return (
    <div className="card">
      <h1>Histórico de execuções</h1>
      <p className="subtitle">Últimas execuções da recuperação de URLs 404.</p>

      {error && <div className="error-box">{error}</div>}

      {jobs && jobs.length === 0 && <div className="empty-state">Nenhuma execução ainda.</div>}

      {jobs && jobs.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>Planilha</th>
              <th>Status</th>
              <th>Redirects válidos</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{new Date(job.createdAt).toLocaleString("pt-BR")}</td>
                <td>{job.filename}</td>
                <td>
                  <span className={`phase-badge ${job.status === "done" ? "done" : job.status === "error" ? "error" : ""}`}>
                    {STATUS_LABELS[job.status]}
                  </span>
                </td>
                <td>{job.stats?.valid_redirects ?? "—"}</td>
                <td>
                  <Link href={`/jobs/${job.id}`}>ver</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
