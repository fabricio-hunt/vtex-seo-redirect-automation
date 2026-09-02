import { NextRequest, NextResponse } from "next/server";
import { isValidSessionCookieValue, SESSION_COOKIE_NAME } from "@/lib/session";

const PUBLIC_PATHS = new Set(["/login", "/backend/auth/login"]);
// Stand-in for Vercel Blob's own public-URL files (lib/localStore.ts, local dev only):
// server-side fetches to these (e.g. the feed cache read in lib/feedCache.ts) don't carry
// the session cookie, same as a real Blob URL wouldn't need one.
const PUBLIC_PATH_PREFIXES = ["/backend/local-files/"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname) || PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  const cookie = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (await isValidSessionCookieValue(cookie)) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/backend/")) {
    return NextResponse.json({ error: "Não autenticado." }, { status: 401 });
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
