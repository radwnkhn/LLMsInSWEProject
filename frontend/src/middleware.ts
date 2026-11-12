import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, isProtectedPath } from "@/lib/session";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isProtectedPath(pathname) && !request.cookies.get(SESSION_COOKIE)?.value) {
    // Next normalizes loopback URLs to localhost. Preserve the browser's host so
    // redirects keep session cookies and API requests on the same local origin.
    const host = request.headers.get("host");
    const origin = host && /^(?:localhost|127(?:\.\d{1,3}){3}|\[::1\])(?::\d+)?$/i.test(host)
      ? `${request.nextUrl.protocol}//${host}` : request.url;
    const login = new URL("/login", origin);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/upload/:path*", "/history/:path*", "/results/:path*", "/admin/:path*", "/compare/:path*", "/settings/:path*",
  "/grading/:path*"] };
