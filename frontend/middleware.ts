import { NextRequest, NextResponse } from "next/server";

// Content Security Policy with a fresh nonce per request: only scripts carrying the nonce can run, and the page
// may only talk to itself and the Startly API. So even injected code couldn't send a visitor's key elsewhere.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function apiOrigins(): string {
  const origin = new URL(API_BASE).origin;
  // 127.0.0.1 and localhost are the same machine but different origins to the browser.
  const alias = origin.includes("127.0.0.1") ? origin.replace("127.0.0.1", "localhost") : origin.includes("localhost") ? origin.replace("localhost", "127.0.0.1") : null;
  return alias ? `${origin} ${alias}` : origin;
}

export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const dev = process.env.NODE_ENV !== "production";
  const csp = [
    "default-src 'self'",
    // 'strict-dynamic' lets Next's nonce'd bootstrap load its own chunks; dev tooling also needs eval.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    // Inline style attributes come from React (bar widths, animations); styles can't run code.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self' ${apiOrigins()}${dev ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  // Next reads the nonce from the request's CSP header and adds it to the scripts it renders.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only: static files and prefetches don't need (and can't use) a per-request nonce.
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
