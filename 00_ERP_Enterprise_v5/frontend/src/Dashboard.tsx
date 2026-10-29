import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { DashboardApi, DashboardApiError, TwinAnomaly, TwinOverview, dashboardApiBase } from './api';
import { clearAuthSession, readAuthSession, saveAuthSession } from './authSession';
import { PlatformModule, WorkspaceView } from './PlatformModules';
import './styles/dashboard.css';

type DashboardData = { overview: TwinOverview; anomalies: TwinAnomaly[] };
const workspaceNavigation: { id: WorkspaceView; label: string; icon: 'home' | 'building' | 'bell' | 'grid' | 'spark' }[] = [
  { id: 'overview', label: 'Centro de mando', icon: 'home' },
  { id: 'assets', label: 'Activos y espacios', icon: 'building' },
  { id: 'signals', label: 'Sensores y señales', icon: 'grid' },
  { id: 'models', label: 'Modelos IFC', icon: 'building' },
  { id: 'maintenance', label: 'Mantenimiento', icon: 'bell' },
  { id: 'intelligence', label: 'Diagnóstico', icon: 'spark' },
];
const workspaceTitles: Record<WorkspaceView, string> = {
  overview: 'Centro de mando',
  assets: 'Activos y espacios',
  signals: 'Sensores y señales',
  models: 'Modelos IFC',
  maintenance: 'Mantenimiento',
  intelligence: 'Diagnóstico',
};

const numberFormat = new Intl.NumberFormat('es-MX');
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });

function formatNumber(value: number | null | undefined): string {
  return value == null ? '—' : numberFormat.format(value);
}

function severityName(severity: string): string {
  const labels: Record<string, string> = {
    critical: 'Crítica',
    high: 'Alta',
    medium: 'Media',
    low: 'Baja',
    warning: 'Alerta',
  };
  return labels[severity.toLowerCase()] ?? severity;
}

function formatMetric(value: number | string | null): string {
  return value == null ? 'Sin lectura' : String(value);
}

function formatDetectedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : dateFormat.format(date);
}

function errorText(error: unknown): string {
  if (error instanceof DashboardApiError) return error.message;
  if (error instanceof TypeError) return 'No fue posible conectar con la API. Comprueba que el servicio esté disponible e inténtalo de nuevo.';
  if (error instanceof Error) return error.message;
  return 'Ocurrió un error inesperado al cargar el centro de mando.';
}

function Icon({ name }: { name: 'home' | 'building' | 'bell' | 'grid' | 'arrow' | 'refresh' | 'logout' | 'check' | 'spark' }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  const paths: Record<typeof name, ReactNode> = {
    home: <><path {...common} d="m3 10 9-7 9 7" /><path {...common} d="M5 9v11h14V9M9 20v-6h6v6" /></>,
    building: <><path {...common} d="M4 21V5l8-2 8 2v16M2 21h20" /><path {...common} d="M8 8h1m6 0h1M8 12h1m6 0h1M8 16h1m6 0h1m-4 5v-5" /></>,
    bell: <><path {...common} d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path {...common} d="M10 21h4" /></>,
    grid: <><rect {...common} x="3" y="3" width="7" height="7" rx="1.5" /><rect {...common} x="14" y="3" width="7" height="7" rx="1.5" /><rect {...common} x="3" y="14" width="7" height="7" rx="1.5" /><rect {...common} x="14" y="14" width="7" height="7" rx="1.5" /></>,
    arrow: <><path {...common} d="M7 17 17 7M7 7h10v10" /></>,
    refresh: <><path {...common} d="M20 7v5h-5M4 17v-5h5" /><path {...common} d="M5.6 9a7 7 0 0 1 11.6-2L20 12M4 12l2.8 5a7 7 0 0 0 11.6-2" /></>,
    logout: <><path {...common} d="M10 17l5-5-5-5M15 12H3" /><path {...common} d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7" /></>,
    check: <><path {...common} d="m5 12 4 4L19 6" /></>,
    spark: <><path {...common} d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" /><path {...common} d="m19 14 .9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9L19 14Z" /></>,
  };

  return <svg aria-hidden="true" viewBox="0 0 24 24" className="icon">{paths[name]}</svg>;
}

function LoginScreen({ onLogin, message }: { onLogin: (tenant: string, email: string, password: string) => Promise<void>; message: string }) {
  const [tenant, setTenant] = useState(() => readAuthSession().tenantId);
  const [email, setEmail] = useState(() => readAuthSession().email);
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onLogin(tenant.trim(), email.trim(), password);
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="brand-mark brand-mark-large">CI</div>
        <p className="eyebrow">CONJUNTO INTELIGENTE</p>
        <h1>Tu operación, en una sola vista.</h1>
        <p className="login-copy">Accede al centro de mando para consultar la salud del gemelo digital y la actividad del conjunto.</p>
        <form className="login-form" onSubmit={(event) => void submit(event)}>
          <label>
            Identificador del tenant
            <input autoComplete="organization" required value={tenant} onChange={(event) => setTenant(event.target.value)} placeholder="ID de tu organización" />
          </label>
          <label>
            Correo electrónico
            <input autoComplete="username" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nombre@empresa.com" />
          </label>
          <label>
            Contraseña
            <input autoComplete="current-password" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Tu contraseña" />
          </label>
          {message && <p className="form-error" role="alert">{message}</p>}
          <button className="button button-primary login-submit" type="submit" disabled={submitting}>
            {submitting ? 'Verificando acceso…' : 'Entrar al centro de mando'}
          </button>
        </form>
        <p className="login-footnote"><span className="status-dot status-dot-green" /> Acceso protegido · Sesión segura</p>
      </section>
      <aside className="login-aside" aria-hidden="true">
        <div className="login-orbit orbit-one" />
        <div className="login-orbit orbit-two" />
        <div className="login-aside-copy">
          <span>VISIÓN OPERATIVA</span>
          <h2>Infraestructura inteligente.<br />Decisiones con contexto.</h2>
          <p>Un punto de entrada para activos, señales y eventos del conjunto.</p>
        </div>
        <div className="login-aside-bottom">GEMELO DIGITAL <span>●</span> OPERACIÓN</div>
      </aside>
    </main>
  );
}

function MetricCard({ label, value, detail, icon, tone = 'default' }: { label: string; value: string; detail: string; icon: 'building' | 'grid' | 'bell' | 'spark'; tone?: string }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-top">
        <span className="metric-icon"><Icon name={icon} /></span>
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-detail">{detail}</span>
    </article>
  );
}

function AnomalyRow({ anomaly }: { anomaly: TwinAnomaly }) {
  const severity = anomaly.severity.toLowerCase();
  return (
    <article className="anomaly-row">
      <span className={`severity-marker severity-${severity}`} />
      <div className="anomaly-main">
        <div className="anomaly-title-line">
          <h3>{anomaly.node_name || anomaly.node_code || 'Activo sin nombre'}</h3>
          <span className={`severity-pill severity-${severity}`}>{severityName(anomaly.severity)}</span>
        </div>
        <p>{anomaly.metric.replaceAll('_', ' ')} · Lectura {formatMetric(anomaly.observed_value)} · Referencia {formatMetric(anomaly.baseline_value)}</p>
        <span className="anomaly-time">{formatDetectedAt(anomaly.detected_at)}</span>
      </div>
    </article>
  );
}

function DashboardContent({ data, onRefresh, refreshing, email, onLogout, view, onViewChange, api, apiError }: {
  data: DashboardData;
  onRefresh: () => void;
  refreshing: boolean;
  email: string;
  onLogout: () => void;
  view: WorkspaceView;
  onViewChange: (view: WorkspaceView) => void;
  api: DashboardApi;
  apiError: string;
}) {
  const { overview, anomalies } = data;
  const idsTotal = overview.bim.ids_pass + overview.bim.ids_fail;
  const health = overview.health.avg;
  const onlineDevices = overview.devices.total
    ? Math.round((overview.devices.online / overview.devices.total) * 100)
    : null;
  const initials = email.slice(0, 2).toUpperCase() || 'CI';
  const bimHref = '/bim/';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Conjunto Inteligente, inicio">
          <span className="brand-mark">CI</span>
          <span className="brand-name">Conjunto<span>Inteligente</span></span>
        </a>
        <div className="workspace-label">ESPACIO DE TRABAJO</div>
        <nav className="side-nav" aria-label="Navegación principal">
          {workspaceNavigation.map((item) => (
            <button key={item.id} className={`nav-item${view === item.id ? ' active' : ''}`} type="button" aria-current={view === item.id ? 'page' : undefined} onClick={() => onViewChange(item.id)}>
              <Icon name={item.icon} /><span>{item.label}</span>
            </button>
          ))}
          <a className="nav-item" href={bimHref}><Icon name="building" /> <span>Gemelo BIM</span><Icon name="arrow" /></a>
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-status">
          <span className="status-dot status-dot-green" />
          <div><strong>API disponible</strong><small>Datos del gemelo digital</small></div>
        </div>
        <button className="profile-button" onClick={onLogout} title={`Cerrar sesión de ${email}`} type="button">
          <span className="avatar">{initials}</span>
          <span className="profile-copy"><strong>{email || 'Sesión activa'}</strong><small>Administración</small></span>
          <Icon name="logout" />
        </button>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs"><span>Conjunto</span><span className="breadcrumb-divider">/</span><strong>{workspaceTitles[view]}</strong></div>
          <div className="topbar-actions">
            <span className={`connection-badge connection-${apiError ? 'offline' : 'online'}`}><span className={`status-dot ${apiError ? 'status-dot-red' : 'status-dot-green'}`} /> API {apiError ? 'sin conexión' : 'conectada'}</span>
            <button className={`icon-button ${refreshing ? 'is-spinning' : ''}`} onClick={onRefresh} disabled={refreshing} type="button" aria-label="Actualizar datos" title="Actualizar datos">
              <Icon name="refresh" />
            </button>
            <button className="avatar avatar-top top-logout" type="button" onClick={onLogout} aria-label={`Cerrar sesión de ${email}`} title="Cerrar sesión">{initials}</button>
          </div>
        </header>

        {view === 'overview' ? <div className="dashboard-content">
          <section className="welcome-row">
            <div>
              <p className="eyebrow">VISTA GENERAL</p>
              <h1>Centro de mando</h1>
              <p className="welcome-subtitle">Estado operativo y actividad reciente de tu conjunto.</p>
            </div>
            <a className="button button-primary" href={bimHref}>Explorar gemelo BIM <Icon name="arrow" /></a>
          </section>

          <section className="hero-card">
            <div className="hero-copy">
              <div className="hero-status"><span className="status-dot status-dot-green" /> VISIÓN DEL CONJUNTO</div>
              <h2>Todo lo que importa,<br /><span>conectado en un solo lugar.</span></h2>
              <p>Consulta activos, sensores y alertas desde una vista operativa unificada.</p>
              <a className="hero-link" href={bimHref}>Abrir gemelo digital <Icon name="arrow" /></a>
            </div>
            <div className="hero-visual" aria-hidden="true">
              <div className="hero-ring ring-back" />
              <div className="hero-ring ring-front" />
              <div className="hero-building">
                <span /><span /><span /><span /><span /><span /><span /><span /><span />
              </div>
              <div className="hero-node node-a" /><div className="hero-node node-b" /><div className="hero-node node-c" />
            </div>
            <div className="hero-footer"><span>CONJUNTO INTELIGENTE</span><span>GEMELO DIGITAL <i /> OPERACIÓN</span></div>
          </section>

          <section className="section-block">
            <div className="section-heading">
              <div><p className="eyebrow">INDICADORES</p><h2>Salud operativa</h2></div>
              <span className="section-caption">Valores reportados por el gemelo digital</span>
            </div>
            <div className="metrics-grid">
              <MetricCard label="Nodos del gemelo" value={formatNumber(overview.nodes_total)} detail={`${formatNumber(overview.bim.bindings)} vínculos IFC`} icon="building" />
              <MetricCard label="Señales saludables" value={`${formatNumber(overview.points.good)} / ${formatNumber(overview.points.total)}`} detail={`${formatNumber(overview.points.stale)} sin actualizar`} icon="grid" tone="green" />
              <MetricCard label="Alertas abiertas" value={formatNumber(overview.open_anomalies)} detail={`${formatNumber(overview.open_anomalies_by_severity.critical ?? 0)} críticas · ${formatNumber(overview.open_anomalies_by_severity.high ?? 0)} altas`} icon="bell" tone={(overview.open_anomalies_by_severity.critical ?? 0) > 0 ? 'red' : overview.open_anomalies ? 'amber' : 'green'} />
              <MetricCard label="Salud promedio" value={health == null ? 'N/D' : `${Math.round(health)}/100`} detail={formatNumber(overview.health.assessed_nodes) + ' activos evaluados'} icon="spark" tone={health != null && health < 40 ? 'red' : 'green'} />
            </div>
          </section>

          <section className="dashboard-columns">
            <article className="panel alerts-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">ATENCIÓN</p><h2>Alertas recientes</h2></div>
                <span className="count-badge">{formatNumber(overview.open_anomalies)} abiertas</span>
              </div>
              {anomalies.length ? (
                <div className="anomaly-list">{anomalies.map((anomaly) => <AnomalyRow key={anomaly.anomaly_id} anomaly={anomaly} />)}</div>
              ) : (
                <div className="empty-state">
                  <span className="empty-icon"><Icon name="check" /></span>
                  <div><strong>{overview.nodes_total ? 'Sin alertas abiertas' : 'Aún no hay actividad registrada'}</strong><p>{overview.nodes_total ? 'No se reportan anomalías pendientes para este conjunto.' : 'Cuando conectes tus activos y señales, su estado aparecerá aquí.'}</p></div>
                </div>
              )}
              {anomalies.length > 0 && <a className="panel-link" href={bimHref}>Ver activos en el gemelo <Icon name="arrow" /></a>}
            </article>

            <article className="panel twin-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">MODELO DIGITAL</p><h2>Gemelo BIM</h2></div>
                <span className="panel-icon"><Icon name="building" /></span>
              </div>
              <div className="model-summary">
                <div className="model-number">{formatNumber(overview.bim.models)}</div>
                <div><strong>{overview.bim.models === 1 ? 'modelo BIM activo' : 'modelos BIM'}</strong><p>{formatNumber(overview.bim.entities)} entidades IFC importadas</p></div>
              </div>
              <div className="health-meter">
                <div className="meter-label"><span>Salud del conjunto</span><strong>{health == null ? 'Sin evaluación' : `${Math.round(health)}%`}</strong></div>
                <div className="meter-track"><span style={{ width: `${Math.min(100, Math.max(0, health ?? 0))}%` }} /></div>
              </div>
              <div className="twin-stats">
                <div><span>Dispositivos en línea</span><strong>{formatNumber(overview.devices.online)} <small>/ {formatNumber(overview.devices.total)}</small></strong></div>
                <div><span>Solicitudes de trabajo</span><strong>{formatNumber(overview.pending_work_requests)} <small>pendientes</small></strong></div>
                <div><span>Validaciones IDS</span><strong>{formatNumber(overview.bim.ids_pass)} <small>/ {formatNumber(idsTotal)}</small></strong></div>
              </div>
              <a className="button button-secondary panel-cta" href={bimHref}>Abrir visor 3D <Icon name="arrow" /></a>
            </article>
          </section>

          <section className="bottom-strip">
            <div className="strip-intro"><span className="strip-icon"><Icon name="grid" /></span><div><strong>Estado de conectividad</strong><span>Lectura de dispositivos y señales</span></div></div>
            <div className="strip-stat"><span>Disponibilidad de dispositivos</span><strong>{onlineDevices == null ? 'Sin dispositivos' : `${onlineDevices}%`}</strong></div>
            <div className="strip-stat"><span>Señales sin lectura</span><strong>{formatNumber(overview.points.never)}</strong></div>
            <div className="strip-stat"><span>Modelos BIM</span><strong>{formatNumber(overview.bim.models)}</strong></div>
          </section>

          <footer className="dashboard-footer"><span>Conjunto Inteligente · Centro de mando</span><span>Los indicadores reflejan información disponible en el backend.</span></footer>
        </div> : <PlatformModule view={view} api={api} bimHref={bimHref} pendingRequests={overview.pending_work_requests} />}
      </main>
    </div>
  );
}

export function Dashboard() {
  const initialSession = readAuthSession();
  const [apiBase, setApiBase] = useState(dashboardApiBase);
  const [token, setToken] = useState(initialSession.token);
  const [email, setEmail] = useState(initialSession.email);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [loginMessage, setLoginMessage] = useState('');
  const [view, setView] = useState<WorkspaceView>('overview');
  const hasData = useRef(false);
  const authRevision = useRef(0);
  const api = useMemo(() => new DashboardApi(apiBase, token), [apiBase, token]);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    const requestToken = token;
    const requestRevision = authRevision.current;
    const isCurrent = () => requestRevision === authRevision.current && readAuthSession().token === requestToken;
    setRefreshing(true);
    if (!hasData.current) setLoading(true);
    setError('');
    try {
      const [overview, anomalies] = await Promise.all([api.overview(), api.anomalies()]);
      if (!isCurrent()) return;
      setData({ overview, anomalies });
      hasData.current = true;
    } catch (reason) {
      if (!isCurrent()) return;
      setError(errorText(reason));
      if (reason instanceof DashboardApiError && reason.status === 401) {
        if (!clearAuthSession(requestToken)) return;
        authRevision.current += 1;
        setData(null);
        hasData.current = false;
        setToken('');
        setLoginMessage('Tu sesión venció. Vuelve a ingresar para consultar el centro de mando.');
      }
    } finally {
      if (isCurrent()) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [api, token]);

  useEffect(() => {
    if (!token) return;
    void loadDashboard();
    const interval = window.setInterval(() => {
      if (!document.hidden) void loadDashboard();
    }, 60_000);
    return () => window.clearInterval(interval);
  }, [loadDashboard, token]);

  async function handleLogin(tenant: string, userEmail: string, password: string) {
    const loginRevision = ++authRevision.current;
    clearAuthSession(undefined, true);
    saveAuthSession({ token: '', tenantId: tenant, email: userEmail });
    setToken('');
    setData(null);
    hasData.current = false;
    setLoading(false);
    setRefreshing(false);
    setError('');
    setLoginMessage('');
    try {
      const nextToken = await api.login(tenant, userEmail, password);
      if (loginRevision !== authRevision.current) return;
      await new DashboardApi(apiBase, nextToken).overview();
      if (loginRevision !== authRevision.current) return;
      saveAuthSession({ token: nextToken, tenantId: tenant, email: userEmail });
      setEmail(userEmail);
      setToken(nextToken);
      setApiBase(dashboardApiBase());
      setData(null);
    } catch (reason) {
      if (loginRevision !== authRevision.current) return;
      saveAuthSession({ token: '', tenantId: tenant, email: userEmail });
      setLoginMessage(errorText(reason));
    }
  }

  function logout() {
    authRevision.current += 1;
    clearAuthSession(undefined, false);
    setToken('');
    setEmail('');
    setData(null);
    hasData.current = false;
    setLoginMessage('');
    setError('');
    setView('overview');
  }

  if (!token) return <LoginScreen onLogin={handleLogin} message={loginMessage} />;

  if (loading && !data) {
    return <main className="loading-page"><span className="loading-spinner" /><p>Conectando con el centro de mando…</p>{error && <div className="load-error" role="alert">{error}<button onClick={logout} type="button">Volver a iniciar sesión</button></div>}</main>;
  }

  if (!data) {
    return <main className="loading-page"><div className="load-error" role="alert">{error || 'No hay información disponible.'}<button onClick={() => void loadDashboard()} type="button">Reintentar</button><button onClick={logout} type="button">Cerrar sesión</button></div></main>;
  }

  return (
    <>
      {error && <div className="global-error" role="alert"><span>{error}</span><button type="button" onClick={() => void loadDashboard()}>Reintentar</button></div>}
      <DashboardContent data={data} onRefresh={() => void loadDashboard()} refreshing={refreshing} email={email} onLogout={logout} view={view} onViewChange={setView} api={api} apiError={error} />
    </>
  );
}
