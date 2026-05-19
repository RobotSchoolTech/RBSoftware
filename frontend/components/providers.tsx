'use client'

import { useEffect } from 'react'
import { api } from '@/lib/api'
import { useAuthStore, useThemeStore } from '@/lib/store'
import type { User } from '@/lib/types'

export function Providers({ children }: { children: React.ReactNode }) {
  const setUser = useAuthStore((s) => s.setUser)
  const setHydrated = useAuthStore((s) => s.setHydrated)
  const theme = useThemeStore((s) => s.theme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    function handleChange(e: MediaQueryListEvent) {
      if (!localStorage.getItem('theme')) {
        useThemeStore.getState().syncFromSystem(e.matches ? 'dark' : 'light')
      }
    }
    mq.addEventListener('change', handleChange)
    return () => mq.removeEventListener('change', handleChange)
  }, [])

  useEffect(() => {
    api
      .get<User>('/auth/me')
      .then((user) => setUser(user))
      .catch(() => setUser(null))
      .finally(() => setHydrated())
  }, [setUser, setHydrated])

  return <>{children}</>
}
