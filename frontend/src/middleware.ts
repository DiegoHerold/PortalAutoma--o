import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/jobs") {
    const url = request.nextUrl.clone();
    url.pathname = "/executions";
    if (!url.searchParams.has("status")) url.searchParams.set("status", "active");
    return NextResponse.redirect(url);
  }

  if (pathname.startsWith("/jobs/")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname.replace(/^\/jobs/, "/executions");
    return NextResponse.redirect(url);
  }

  if (pathname === "/dispatch") {
    const url = request.nextUrl.clone();
    url.pathname = "/executions";
    url.searchParams.set("status", "waiting");
    url.searchParams.delete("limit");
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/automations/:path*", "/executions/:path*", "/jobs/:path*", "/dispatch"],
};
