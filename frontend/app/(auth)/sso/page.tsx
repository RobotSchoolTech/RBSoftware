'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { User } from '@/lib/types'

const PORTAL_LOGIN_URL =
  process.env.NEXT_PUBLIC_DEV_LOGIN === 'true'
    ? '/login'
    : 'https://app.miel-robotschool.com/?next=lms'

function SSOContent() {
  const router = useRouter()
  const params = useSearchParams()
  const setUser = useAuthStore((s) => s.setUser)
  const [error, setError] = useState<string | null>(null)
  const canjeado = useRef(false)

  useEffect(() => {
    // Guardia: el token SSO es single-use. Sin esto, StrictMode (dev) corre
    // el efecto dos veces → doble POST de canje → el 2.º falla con "sin acceso".
    if (canjeado.current) return
    canjeado.current = true

    const token = params.get('token')
    if (!token) {
      window.location.href = PORTAL_LOGIN_URL
      return
    }

    api
      .post<{ ok: boolean }>('/auth/sso/login', { token })
      .then(async () => {
        const user = await api.get<User>('/auth/me')
        setUser(user)
        router.replace('/dashboard')
      })
      .catch(() => {
        setError('Tu cuenta no tiene acceso al LMS. Contacta al administrador.')
      })
  }, [])

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/40">
        <div className="w-full max-w-sm space-y-4 rounded-xl border bg-card p-8 shadow-sm text-center">
          <p className="text-sm text-destructive">{error}</p>
          <a href={PORTAL_LOGIN_URL} className="text-sm text-primary underline">
            Volver al portal
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-primary" />
        <p className="text-sm text-muted-foreground">Iniciando sesión…</p>
      </div>
    </div>
  )
}

export default function SSOPage() {
  return (
    <Suspense>
      <SSOContent />
    </Suspense>
  )
}
