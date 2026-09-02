import type { Metadata } from "next";
import Link from "next/link";
import { LogoutButton } from "./LogoutButton";
import "./globals.css";

export const metadata: Metadata = {
  title: "404 URL Recovery",
  description: "Recupera URLs 404 mapeando para páginas de produto ativas e gera redirects para o VTEX.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <nav className="nav">
          <Link href="/upload" className="brand">
            404 URL Recovery
          </Link>
          <div className="nav-links">
            <Link href="/upload">Nova execução</Link>
            <Link href="/history">Histórico</Link>
            <LogoutButton />
          </div>
        </nav>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
