"use client";

import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    await fetch("/backend/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <a onClick={handleLogout} style={{ cursor: "pointer" }}>
      Sair
    </a>
  );
}
