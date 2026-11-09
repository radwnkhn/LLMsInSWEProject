import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, isProtectedPath } from "@/lib/session";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isProtectedPath(pathname) && !request.cookies.get(SESSION_COOKIE)?.value) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/upload/:path*", "/history/:path*", "/results/:path*", "/admin/:path*", "/compare/:path*"] };
