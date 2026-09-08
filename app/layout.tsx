import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { LogoutButton } from "./LogoutButton";
import { Sidebar } from "./Sidebar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains-mono" });

export const metadata: Metadata = {
  title: "404 URL Recovery",
  description: "Recupera URLs 404 mapeando para páginas de produto ativas e gera redirects para o VTEX.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <div className="app-shell">
          <header className="topbar">
            <div className="topbar-breadcrumb">
              <Link href="/upload" className="brand">
                404 URL Recovery
              </Link>
            </div>
            <div className="topbar-actions">
              <LogoutButton />
            </div>
          </header>
          <div className="app-body">
            <Sidebar />
            <main className="main-content">
              <div className="container">{children}</div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
