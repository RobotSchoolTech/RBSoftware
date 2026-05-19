import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_PATHS = ['/sso', '/training/verify']

/** Routes that require specific roles. ADMIN always passes. */
const ROUTE_ROLES: [string, string[]][] = [
  ['/academic/schools', ['ADMIN']],
  ['/academic/grades', ['ADMIN', 'DIRECTOR']],
  ['/academic/courses', ['ADMIN', 'DIRECTOR', 'TEACHER', 'STUDENT']],
  ['/settings', ['ADMIN']],
  ['/orders', ['ADMIN', 'COMERCIAL']],
  ['/catalog', ['ADMIN', 'COMERCIAL']],
  ['/inventory', ['ADMIN', 'OPERATIVO']],
  ['/production', ['ADMIN', 'OPERATIVO']],
  ['/fulfillment', ['ADMIN', 'OPERATIVO']],
  ['/reports', ['ADMIN']],
  ['/training/grading', ['ADMIN', 'TRAINER', 'SUPER_TRAINER']],
  ['/training/programs', ['ADMIN', 'TRAINER', 'SUPER_TRAINER', 'TEACHER']],
  ['/training/my-programs', ['ADMIN', 'TEACHER']],
  ['/training/certificates', ['ADMIN', 'TEACHER']],
  ['/repository', ['ADMIN', 'TRAINER', 'SUPER_TRAINER', 'TEACHER']],
]

function parseRoles(cookie: string | undefined): string[] {
  if (!cookie) return []
  try {
    let parsed = JSON.parse(cookie)
    // FastAPI wraps JSON cookie values in extra quotes — parse again if needed
    if (typeof parsed === 'string') parsed = JSON.parse(parsed)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get('access_token')
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p))

  // Not authenticated → portal (con ?next=lms para auto-redirect tras login)
  if (!token && !isPublic) {
    return NextResponse.redirect('https://app.miel-robotschool.com?next=lms')
  }

  // Role-based route protection
  if (token) {
    const roles = parseRoles(request.cookies.get('user_roles')?.value)
    for (const [route, allowed] of ROUTE_ROLES) {
      if (pathname === route || pathname.startsWith(route + '/') || pathname.startsWith(route + '?')) {
        const hasAccess = allowed.some((r) => roles.includes(r))
        if (!hasAccess) {
          const url = request.nextUrl.clone()
          url.pathname = '/dashboard'
          url.searchParams.set('error', 'unauthorized')
          return NextResponse.redirect(url)
        }
        break
      }
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
