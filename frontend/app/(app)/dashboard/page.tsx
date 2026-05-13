'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  BookOpen,
  CheckCircle,
  ClipboardList,
  Layers,
  TrendingDown,
  TrendingUp,
  Users2,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ErrorBanner } from '@/components/error-banner'
import { api } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type {
  CourseRead,
  Grade,
  GradeWithCourses,
  StudentUnitContent,
} from '@/lib/types'

// ── StatCard ─────────────────────────────────────────────────────────────────

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  gradient,
  trend,
  href,
}: {
  title: string
  value: number | string
  subtitle: string
  icon: React.ElementType
  gradient: string
  trend?: { value: number; isPositive: boolean }
  href?: string
}) {
  const card = (
    <div
      className={`relative overflow-hidden rounded-xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 hover:-translate-y-1 ${gradient}`}
    >
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium text-white/90">{title}</p>
        <div className="p-2 rounded-lg bg-white/20 backdrop-blur-sm">
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
      <p className="text-3xl font-bold text-white">{value}</p>
      <p className="text-sm text-white/70 mt-1">{subtitle}</p>
      {trend && (
        <div className="inline-flex items-center gap-1 mt-3 px-2 py-1 rounded-full text-xs font-medium bg-white/20 text-white">
          {trend.isPositive ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {trend.value}%
        </div>
      )}
    </div>
  )

  if (href) {
    return (
      <Link href={href} className="block">
        {card}
      </Link>
    )
  }
  return card
}

// ── Role-specific panels ─────────────────────────────────────────────────────

function ConnStatsSection({ title }: { title: string }) {
  const [connStats, setConnStats] = useState<any>(null)
  const [connDays, setConnDays] = useState(7)
  const [loadingConn, setLoadingConn] = useState(false)

  useEffect(() => {
    setLoadingConn(true)
    api
      .get(`/auth/users/connection-stats?days=${connDays}`)
      .then(setConnStats)
      .catch(() => {})
      .finally(() => setLoadingConn(false))
  }, [connDays])

  return (
    <div className="mt-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">Inicios de sesión por día</p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setConnDays(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                connDays === d ? 'bg-primary text-white' : 'border hover:bg-muted'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loadingConn ? (
        <div className="h-64 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : connStats ? (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border bg-card p-4 text-center">
              <p className="text-3xl font-bold text-primary">{connStats.total_logins}</p>
              <p className="text-xs text-muted-foreground mt-1">Inicios de sesión</p>
            </div>
            <div className="rounded-xl border bg-card p-4 text-center">
              <p className="text-3xl font-bold text-green-600">{connStats.unique_users}</p>
              <p className="text-xs text-muted-foreground mt-1">Usuarios únicos</p>
            </div>
            <div className="rounded-xl border bg-card p-4 text-center">
              <p className="text-3xl font-bold text-orange-500">{connStats.total_logouts}</p>
              <p className="text-xs text-muted-foreground mt-1">Cierres de sesión</p>
            </div>
          </div>

          <div className="rounded-xl border bg-card p-6">
            <h3 className="text-sm font-semibold mb-4">Conexiones diarias</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={connStats.logins_by_day}
                margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) =>
                    new Date(v).toLocaleDateString('es', {
                      day: '2-digit',
                      month: 'short',
                    })
                  }
                />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  formatter={(value) => [value, 'Conexiones']}
                  labelFormatter={(label) =>
                    new Date(label).toLocaleDateString('es', {
                      weekday: 'long',
                      day: 'numeric',
                      month: 'long',
                    })
                  }
                />
                <Line
                  type="monotone"
                  dataKey="logins"
                  stroke="#1A237E"
                  strokeWidth={2}
                  dot={{ fill: '#FF6F00', strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border bg-card p-6">
              <h3 className="text-sm font-semibold mb-4">Conexiones por hora del día</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={connStats.logins_by_hour}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(h) =>
                      h % 3 === 0
                        ? h === 0 ? '12am' : h < 12 ? `${h}am` : h === 12 ? '12pm' : `${h - 12}pm`
                        : ''
                    }
                  />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    formatter={(value) => [value, 'Conexiones']}
                    labelFormatter={(h) =>
                      h === 0 ? '12:00 am' : h < 12 ? `${h}:00 am` : h === 12 ? '12:00 pm' : `${h - 12}:00 pm`
                    }
                  />
                  <Bar dataKey="logins" fill="#1A237E" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

          {connStats.top_users.length > 0 && (
            <div className="rounded-xl border bg-card p-6">
              <h3 className="text-sm font-semibold mb-4">Usuarios más activos</h3>
              <div className="space-y-2">
                {connStats.top_users.map((u: any, i: number) => (
                  <div
                    key={u.user_id}
                    className="flex items-center gap-3 py-2 border-b last:border-0"
                  >
                    <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">
                      {i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{u.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-bold text-primary">{u.login_count}</p>
                      <p className="text-xs text-muted-foreground">conexiones</p>
                    </div>
                    <div className="w-20 hidden md:block">
                      <div className="h-1.5 rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{
                            width: `${(
                              (u.login_count / connStats.top_users[0].login_count) *
                              100
                            ).toFixed(0)}%`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
          No hay datos de conexión disponibles
        </div>
      )}
    </div>
  )
}

function AdminPanel() {
  return <ConnStatsSection title="Actividad de conexiones" />
}

function OperativoPanel() {
  return (
    <p className="text-muted-foreground text-sm">Próximamente.</p>
  )
}

function ComercialPanel() {
  return (
    <p className="text-muted-foreground text-sm">Próximamente.</p>
  )
}

function TeacherPanel() {
  const [stats, setStats] = useState({
    activeCourses: 0,
    pendingGrading: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const courses = await api.get<CourseRead[]>('/academic/my-courses')
      setStats((prev) => ({
        ...prev,
        activeCourses: courses.filter((c) => c.is_active).length,
      }))
    } catch (err: any) {
      setError(err?.detail ?? 'Error al cargar el dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <SkeletonCards count={2} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      <StatCard
        title="Mis Cursos Activos"
        value={stats.activeCourses}
        subtitle="Cursos asignados"
        icon={BookOpen}
        gradient="bg-gradient-to-br from-blue-500 to-blue-700"
        href="/academic/courses"
      />
      <StatCard
        title="Por Calificar"
        value={stats.pendingGrading}
        subtitle="Entregas pendientes de nota"
        icon={ClipboardList}
        gradient="bg-gradient-to-br from-amber-500 to-amber-700"
      />
    </div>
  )
}

function DirectorPanel() {
  const [stats, setStats] = useState({
    gradesCount: 0,
    totalStudents: 0,
    activeCourses: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const grades = await api.get<Grade[]>('/academic/my-grades')
      let totalStudents = 0
      let activeCourses = 0
      const details = await Promise.all(
        grades.map((g) =>
          api.get<GradeWithCourses>(`/academic/grades/${g.public_id}`),
        ),
      )
      for (const d of details) {
        activeCourses += d.courses.filter((c) => c.is_active).length
        const courseDetails = await Promise.all(
          d.courses.map((c) =>
            api
              .get<{ public_id: string }[]>(
                `/academic/courses/${c.public_id}/students`,
              )
              .catch(() => [] as { public_id: string }[]),
          ),
        )
        for (const students of courseDetails) {
          totalStudents += students.length
        }
      }
      setStats({
        gradesCount: grades.length,
        totalStudents,
        activeCourses,
      })
    } catch (err: any) {
      setError(err?.detail ?? 'Error al cargar el dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <SkeletonCards count={3} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <StatCard
          title="Mis Grados"
          value={stats.gradesCount}
          subtitle="Grados asignados"
          icon={Layers}
          gradient="bg-gradient-to-br from-purple-500 to-purple-700"
          href="/academic/grades"
        />
        <StatCard
          title="Total Estudiantes"
          value={stats.totalStudents}
          subtitle="En mis grados"
          icon={Users2}
          gradient="bg-gradient-to-br from-pink-500 to-pink-700"
        />
        <StatCard
          title="Cursos Activos"
          value={stats.activeCourses}
          subtitle="En mis grados"
          icon={BookOpen}
          gradient="bg-gradient-to-br from-blue-500 to-blue-700"
        />
      </div>
      <ConnStatsSection title="Actividad de mis estudiantes y docentes" />
    </div>
  )
}

function StudentPanel() {
  const [stats, setStats] = useState({
    coursesCount: 0,
    pendingAssignments: 0,
    gradedThisWeek: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const courses = await api.get<CourseRead[]>('/academic/my-courses')
      let pending = 0
      let gradedWeek = 0
      const now = new Date()
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

      const allContent = await Promise.all(
        courses.map((c) =>
          api
            .get<StudentUnitContent[]>(
              `/academic/courses/${c.public_id}/content`,
            )
            .catch(() => [] as StudentUnitContent[]),
        ),
      )

      for (const units of allContent) {
        for (const unit of units) {
          for (const a of unit.assignments) {
            if (!a.my_submission) {
              pending++
            } else if (
              a.my_submission.status === 'GRADED' &&
              a.my_submission.graded_at &&
              new Date(a.my_submission.graded_at) >= weekAgo
            ) {
              gradedWeek++
            }
          }
        }
      }

      setStats({
        coursesCount: courses.length,
        pendingAssignments: pending,
        gradedThisWeek: gradedWeek,
      })
    } catch (err: any) {
      setError(err?.detail ?? 'Error al cargar el dashboard.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) return <SkeletonCards count={3} />
  if (error) return <ErrorBanner message={error} onRetry={load} />

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      <StatCard
        title="Mis Cursos"
        value={stats.coursesCount}
        subtitle="Cursos matriculados"
        icon={BookOpen}
        gradient="bg-gradient-to-br from-blue-500 to-blue-700"
        href="/academic/courses"
      />
      <StatCard
        title="Tareas Pendientes"
        value={stats.pendingAssignments}
        subtitle="Sin entregar"
        icon={ClipboardList}
        gradient="bg-gradient-to-br from-rose-500 to-rose-700"
      />
      <StatCard
        title="Calificadas esta Semana"
        value={stats.gradedThisWeek}
        subtitle="Últimos 7 días"
        icon={CheckCircle}
        gradient="bg-gradient-to-br from-emerald-500 to-emerald-700"
      />
    </div>
  )
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCards({ count }: { count: number }) {
  const cols =
    count === 2
      ? 'lg:grid-cols-2'
      : count === 3
        ? 'lg:grid-cols-3'
        : 'lg:grid-cols-4'
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 ${cols} gap-6`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-36 rounded-xl bg-muted animate-pulse" />
      ))}
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const ROLE_SUBTITLES: Record<string, string> = {
  ADMIN: 'Panel de administración — RBSoftware',
  DIRECTOR: 'Panel de dirección académica',
  TEACHER: 'Panel docente',
  STUDENT: 'Tu espacio de aprendizaje',
  OPERATIVO: 'Panel operativo',
  COMERCIAL: 'Panel comercial',
}

function getSubtitle(roles: string[]): string {
  for (const role of [
    'ADMIN',
    'DIRECTOR',
    'TEACHER',
    'STUDENT',
    'OPERATIVO',
    'COMERCIAL',
  ]) {
    if (roles.includes(role)) return ROLE_SUBTITLES[role]
  }
  return 'Bienvenido'
}

function getPanelForRoles(roles: string[]) {
  if (roles.includes('ADMIN')) return <AdminPanel />
  if (roles.includes('OPERATIVO')) return <OperativoPanel />
  if (roles.includes('COMERCIAL')) return <ComercialPanel />
  if (roles.includes('DIRECTOR')) return <DirectorPanel />
  if (roles.includes('TEACHER')) return <TeacherPanel />
  if (roles.includes('STUDENT')) return <StudentPanel />
  return null
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardContent() {
  const searchParams = useSearchParams()
  const unauthorizedError = searchParams.get('error') === 'unauthorized'
  const { user, roles } = useAuthStore()

  return (
    <div className="space-y-6">
      {unauthorizedError && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900 dark:bg-red-950/30">
          <p className="text-sm text-red-700 dark:text-red-400">
            No tienes permisos para acceder a esa sección. Si crees que esto es
            un error, cierra sesión y vuelve a ingresar.
          </p>
          <button
            onClick={async () => {
              await api.post('/auth/logout').catch(() => {})
              window.location.href = '/login'
            }}
            className="shrink-0 text-xs font-medium text-red-700 hover:underline dark:text-red-400"
          >
            Cerrar sesión →
          </button>
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground">
            Bienvenido, {user?.first_name ?? ''} 👋
          </h1>
          <p className="text-muted-foreground mt-1">{getSubtitle(roles)}</p>
        </div>
      </div>

      {getPanelForRoles(roles)}
    </div>
  )
}
