'use client'

import { useEffect, useRef } from 'react'
import { useAuthStore } from '@/lib/store'
import type { User } from '@/lib/types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/**
 * Hidrata la sesión consultando /auth/me. Se monta SOLO dentro del shell
 * autenticado (app)/layout, nunca en el root: así las rutas públicas
 * (/login, /sso) no disparan /auth/me y no compiten con el canje de token
 * del SSO (el race que rebotaba el dashboard al portal).
 */
export function AuthBootstrap() {
  const setUser = useAuthStore((s) => s.setUser)
  const setHydrated = useAuthStore((s) => s.setHydrated)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    // fetch directo para evitar el auto-redirect de api.ts cuando no hay sesión
    fetch(`${BASE}/auth/me`, { credentials: 'include' })
      .then(async (res) => {
        if (res.ok) {
          const user: User = await res.json()
          setUser(user)
        } else {
          setUser(null)
        }
      })
      .catch(() => setUser(null))
      .finally(() => setHydrated())
  }, [setUser, setHydrated])

  return null
}
