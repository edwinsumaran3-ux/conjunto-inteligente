import { FormEvent, ReactNode, useEffect, useState } from 'react';
import {
  DashboardApi,
  DashboardApiError,
  MaintenanceOrder,
  MaintenanceOrderStatus,
  MaintenancePage,
  MaintenanceResident,
  MaintenanceUnit,
  MaintenanceVendor,
  ResidentWrite,
  SensorSimulationProfile,
  SimulatedDevice,
  TenantUser,
  TwinAnomaly,
  TwinModelVersion,
  TwinNode,
  TwinPoint,
  VendorWrite,
} from './api';
import './styles/platformModules.css';

export type WorkspaceView = 'overview' | 'assets' | 'signals' | 'models' | 'maintenance' | 'intelligence';

const numberFormat = new Intl.NumberFormat('es-MX');
const dateFormat = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' });

const pages: Record<Exclude<WorkspaceView, 'overview'>, { eyebrow: string; title: string; description: string }> = {
  assets: { eyebrow: 'INVENTARIO DEL CONJUNTO', title: 'Activos y espacios', description: 'Consulta la jerarquía, ubicación y estado registrados para los nodos del gemelo digital.' },
  signals: { eyebrow: 'INTEGRACIÓN OPERATIVA', title: 'Sensores y señales', description: 'Revisa lecturas, calidad y frescura de los puntos conectados al modelo operativo.' },
  models: { eyebrow: 'OPENBIM · CDE', title: 'Modelos y documentos IFC', description: 'Consulta las versiones importadas y continúa la carga o revisión desde el visor BIM existente.' },
  maintenance: { eyebrow: 'OPERACIÓN Y MANTENIMIENTO', title: 'Órdenes e incidencias', description: 'Registra solicitudes y consulta órdenes operativas; las aprobaciones y transiciones se validan en el ERP.' },
  intelligence: { eyebrow: 'DIAGNÓSTICO ASISTIDO', title: 'Análisis y dependencias', description: 'Explora el contexto de diagnóstico disponible sin confundir correlaciones con causas demostradas.' },
};

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : 'No fue posible consultar el servicio.';
}

function showDate(value: string | null | undefined): string {
  if (!value) return 'Sin registro';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha no disponible' : dateFormat.format(date);
}

function pretty(value: string | null | undefined): string {
  return value ? value.replaceAll('_', ' ').toLowerCase() : 'No especificado';
}

function ModuleFrame({ view, bimHref, children }: { view: Exclude<WorkspaceView, 'overview'>; bimHref: string; children: ReactNode }) {
  const page = pages[view];
  return (
    <section className="module-page">
      <header className="module-heading">
        <div><p className="eyebrow">{page.eyebrow}</p><h1>{page.title}</h1><p>{page.description}</p></div>
        <a className="button button-secondary" href={bimHref}>Abrir visor BIM <span aria-hidden="true">↗</span></a>
      </header>
      {children}
    </section>
  );
}

function ModuleError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="module-error" role="alert"><span>{message}</span><button type="button" onClick={onRetry}>Reintentar</button></div>;
}

function EmptyModule({ title, detail }: { title: string; detail: string }) {
  return <div className="module-empty"><strong>{title}</strong><p>{detail}</p></div>;
}

function AssetsModule({ api, bimHref }: { api: DashboardApi; bimHref: string }) {
  const [items, setItems] = useState<TwinNode[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const pageSize = 50;

  async function load(nextOffset = offset, query = appliedSearch) {
    setLoading(true);
    setError('');
    try {
      const result = await api.nodes({ limit: pageSize, offset: nextOffset, search: query });
      setItems(result.items);
      setTotal(result.total);
      setOffset(result.offset);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(0, ''); }, [api]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedSearch(search);
    void load(0, search);
  }

  return (
    <ModuleFrame view="assets" bimHref={bimHref}>
      <div className="module-toolbar">
        <form className="module-search" onSubmit={submitSearch}>
          <label htmlFor="asset-search">Buscar por nombre o código</label>
          <div><input id="asset-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Ej. Bomba, Torre A…" /><button type="submit">Buscar</button></div>
        </form>
        <span className="module-result-count">{numberFormat.format(total)} activos y espacios</span>
      </div>
      {error && <ModuleError message={error} onRetry={() => void load()} />}
      {loading ? <div className="module-loading">Consultando inventario…</div> : items.length ? (
        <div className="module-table-wrap"><table className="module-table">
          <thead><tr><th>Elemento</th><th>Tipo</th><th>Ubicación superior</th><th>Estado</th><th>Coordenadas</th></tr></thead>
          <tbody>{items.map((node) => <tr key={node.id}>
            <td><strong>{node.name}</strong><small>{node.code}</small></td>
            <td>{pretty(node.node_type)}</td><td>{node.parent_name || 'Sin espacio padre'}</td>
            <td><span className={`module-state state-${node.status.toLowerCase()}`}>{pretty(node.status)}</span></td>
            <td>{node.latitude == null || node.longitude == null ? 'No registradas' : `${node.latitude.toFixed(5)}, ${node.longitude.toFixed(5)}`}</td>
          </tr>)}</tbody>
        </table></div>
      ) : !error ? <EmptyModule title={appliedSearch ? 'No hay coincidencias' : 'Aún no hay activos en el inventario'} detail="Los elementos aparecerán aquí al registrarlos o al importar un modelo IFC con sus identificadores." /> : null}
      <div className="module-pagination"><span>{total ? `${offset + 1}–${Math.min(offset + pageSize, total)} de ${total}` : 'Sin resultados'}</span><div>
        <button type="button" disabled={loading || offset === 0} onClick={() => void load(Math.max(0, offset - pageSize))}>Anterior</button>
        <button type="button" disabled={loading || offset + pageSize >= total} onClick={() => void load(offset + pageSize)}>Siguiente</button>
      </div></div>
    </ModuleFrame>
  );
}

function SignalsModule({ api, bimHref }: { api: DashboardApi; bimHref: string }) {
  const [points, setPoints] = useState<TwinPoint[]>([]);
  const [nodes, setNodes] = useState<TwinNode[]>([]);
  const [profiles, setProfiles] = useState<SensorSimulationProfile[]>([]);
  const [simulatedDevices, setSimulatedDevices] = useState<SimulatedDevice[]>([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [selectedProfile, setSelectedProfile] = useState('');
  const [sensorCode, setSensorCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [simulationError, setSimulationError] = useState('');
  const [simulationMessage, setSimulationMessage] = useState('');
  const [simulationBusy, setSimulationBusy] = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [nextPoints, nextNodes, nextProfiles, nextDevices] = await Promise.all([
        api.points(200),
        api.nodes({ limit: 500 }),
        api.simulatorProfiles(),
        api.simulatedDevices(),
      ]);
      setPoints(nextPoints);
      setNodes(nextNodes.items);
      setProfiles(nextProfiles);
      setSimulatedDevices(nextDevices);
      setSelectedNode((current) => current || nextNodes.items[0]?.id || '');
      setSelectedProfile((current) => current || nextProfiles[0]?.profile_id || '');
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [api]);
  const fresh = points.filter((point) => point.freshness === 'FRESH').length;
  const stale = points.filter((point) => point.freshness === 'STALE').length;
  const noData = points.filter((point) => point.freshness === 'NO_DATA').length;

  async function createSensor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const profile = profiles.find((item) => item.profile_id === selectedProfile);
    if (!selectedNode || !profile) return;
    setSimulationBusy(true);
    setSimulationError('');
    setSimulationMessage('');
    try {
      const code = sensorCode.trim() || `SIM-${profile.profile_id}-${crypto.randomUUID().slice(0, 8)}`;
      const created = await api.createSimulatedDevice({
        node_id: selectedNode,
        profile_id: profile.profile_id,
        code,
      });
      setSensorCode('');
      setSimulationMessage(`Sensor virtual ${created.code} creado. No hay hardware físico conectado.`);
      await load();
    } catch (reason) {
      setSimulationError(messageFrom(reason));
    } finally {
      setSimulationBusy(false);
    }
  }

  async function runSimulation(device: SimulatedDevice, scenario: 'normal' | 'alarm') {
    setSimulationBusy(true);
    setSimulationError('');
    setSimulationMessage('');
    try {
      const result = await api.runSimulation(device.device_id, scenario, crypto.randomUUID());
      const anomalies = result.diagnostic?.anomalies_created_or_updated ?? 0;
      setSimulationMessage(
        result.status === 'duplicate'
          ? 'Esta ejecución ya había sido procesada; no se duplicaron lecturas.'
          : `${result.samples.length} lecturas sintéticas procesadas${anomalies ? `; ${anomalies} anomalía(s) registrada(s)` : ''}.`,
      );
      await load();
    } catch (reason) {
      setSimulationError(messageFrom(reason));
    } finally {
      setSimulationBusy(false);
    }
  }

  return (
    <ModuleFrame view="signals" bimHref={bimHref}>
      <section className="simulator-panel" aria-labelledby="sensor-simulator-title">
        <div className="simulator-heading">
          <div>
            <p className="eyebrow">LABORATORIO · SOLO SIMULACIÓN</p>
            <h2 id="sensor-simulator-title">Prueba la operación sin sensores físicos</h2>
            <p>Los dispositivos virtuales usan el registro, la telemetría y el diagnóstico existentes del gemelo digital.</p>
          </div>
          <span className="simulator-badge">DATOS SINTÉTICOS</span>
        </div>
        <form className="simulator-form" onSubmit={(event) => void createSensor(event)}>
          <label>
            Torre, espacio o activo
            <select required value={selectedNode} onChange={(event) => setSelectedNode(event.target.value)} disabled={!nodes.length || simulationBusy}>
              <option value="">Selecciona un nodo</option>
              {nodes.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.code} · {pretty(node.node_type)}</option>)}
            </select>
          </label>
          <label>
            Tipo de sensor virtual
            <select required value={selectedProfile} onChange={(event) => setSelectedProfile(event.target.value)} disabled={!profiles.length || simulationBusy}>
              {profiles.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.name} ({profile.unit})</option>)}
            </select>
          </label>
          <label>
            Código del punto
            <input value={sensorCode} onChange={(event) => setSensorCode(event.target.value)} maxLength={180} placeholder="Se genera automáticamente si queda vacío" disabled={simulationBusy} />
          </label>
          <button type="submit" className="button button-primary" disabled={!nodes.length || !profiles.length || simulationBusy}>
            {simulationBusy ? 'Procesando…' : 'Crear sensor virtual'}
          </button>
        </form>
        {simulationError && <div className="simulator-feedback simulator-error" role="alert">{simulationError}</div>}
        {simulationMessage && <div className="simulator-feedback" role="status">{simulationMessage}</div>}
        {!nodes.length && !loading && <p className="module-note">Primero importa un modelo IFC o registra espacios y activos en el gemelo digital.</p>}
        <p className="simulator-safety-note">Toda lectura queda marcada como simulada. Las alarmas de humo y ascensor son demostraciones de software y no sustituyen sistemas certificados ni accionan equipos reales.</p>
        {simulatedDevices.length > 0 && (
          <div className="simulator-device-list">
            {simulatedDevices.map((device) => {
              const profile = profiles.find((item) => item.profile_id === device.profile_id);
              return (
                <article className="simulator-device" key={device.device_id}>
                  <div className="simulator-device-info">
                    <strong>{device.name}</strong>
                    <span>{device.code} · {device.node_name} · {pretty(device.semantic_kind)}</span>
                    <small>
                      {device.latest_value == null ? 'Sin lecturas todavía' : `${device.latest_value} ${device.latest_unit || device.unit}`}
                      {device.latest_quality ? ` · ${device.latest_quality}` : ''}
                      {device.latest_observed_at ? ` · ${showDate(device.latest_observed_at)}` : ''}
                    </small>
                  </div>
                  <div className="simulator-device-actions">
                    <button type="button" disabled={simulationBusy} onClick={() => void runSimulation(device, 'normal')}>Lectura normal</button>
                    {profile?.supports_alarm && <button type="button" className="simulator-alarm-button" disabled={simulationBusy} onClick={() => void runSimulation(device, 'alarm')}>Simular alarma</button>}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
      <div className="module-summary-grid">
        <div><span>Puntos consultados</span><strong>{numberFormat.format(points.length)}</strong></div>
        <div><span>Lectura vigente</span><strong className="text-green">{numberFormat.format(fresh)}</strong></div>
        <div><span>Lectura vencida</span><strong className="text-amber">{numberFormat.format(stale)}</strong></div>
        <div><span>Sin datos</span><strong>{numberFormat.format(noData)}</strong></div>
      </div>
      {error && <ModuleError message={error} onRetry={() => void load()} />}
      {loading ? <div className="module-loading">Consultando señales…</div> : points.length ? (
        <div className="module-table-wrap"><table className="module-table">
          <thead><tr><th>Punto</th><th>Activo</th><th>Lectura actual</th><th>Calidad</th><th>Frescura</th><th>Última observación</th></tr></thead>
          <tbody>{points.map((point) => <tr key={point.id}>
            <td><strong>{point.name}</strong><small>{point.code} · {pretty(point.semantic_kind)}</small></td>
            <td className="identifier-cell">{point.node_id}</td>
            <td>{point.value == null ? 'Sin lectura' : `${point.value} ${point.unit || point.canonical_unit || ''}`}</td>
            <td>{point.quality || point.quality_reason || 'No informada'}</td>
            <td><span className={`module-state state-${point.freshness.toLowerCase()}`}>{pretty(point.freshness)}</span></td>
            <td>{showDate(point.observed_at)}</td>
          </tr>)}</tbody>
        </table></div>
      ) : !error ? <EmptyModule title="No hay puntos de telemetría registrados" detail="Crea un sensor virtual arriba para probar el flujo sin hardware. Las lecturas físicas aparecerán cuando se conecte un sensor o sistema de origen real." /> : null}
      <p className="module-note">La lectura y su hora provienen del servicio. La plataforma no infiere valores cuando no hay datos disponibles.</p>
    </ModuleFrame>
  );
}

function ModelsModule({ api, bimHref }: { api: DashboardApi; bimHref: string }) {
  const [models, setModels] = useState<TwinModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try { setModels(await api.modelVersions()); } catch (reason) { setError(messageFrom(reason)); } finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [api]);

  return (
    <ModuleFrame view="models" bimHref={bimHref}>
      <div className="module-action-banner"><div><strong>Importar o revisar un IFC</strong><p>El visor existente valida y carga el archivo, conserva la versión y muestra la geometría y jerarquía disponibles.</p></div><a className="button button-primary" href={bimHref}>Ir a carga IFC <span aria-hidden="true">↗</span></a></div>
      {error && <ModuleError message={error} onRetry={() => void load()} />}
      {loading ? <div className="module-loading">Consultando versiones del modelo…</div> : models.length ? (
        <div className="model-version-list">{models.map((model) => <article className="model-version-card" key={model.id}>
          <span className="model-version-icon" aria-hidden="true">IFC</span>
          <div className="model-version-info"><h2>{model.model_key} <span>v{model.version}</span></h2><p>{model.filename || 'Documento IFC'} · {model.source_format} · {numberFormat.format(model.entity_count)} entidades</p><small>Importado {showDate(model.created_at)} · {model.lifecycle_status}</small></div>
          <span className={`module-state ${model.has_file ? 'state-fresh' : 'state-no_data'}`}>{model.has_file ? 'Archivo disponible' : 'Sin archivo'}</span>
        </article>)}</div>
      ) : !error ? <EmptyModule title="Todavía no hay modelos importados" detail="Carga un IFC real desde el visor. Se conservará la estructura y el contenido que el archivo aporte; las propiedades ausentes quedarán identificadas como faltantes." /> : null}
      <p className="module-note">Los archivos de planos PDF o imágenes no se convierten automáticamente en geometría BIM. La extracción asistida requerirá revisión y validación del equipo responsable.</p>
    </ModuleFrame>
  );
}

const orderStatuses: MaintenanceOrderStatus[] = [
  'pending_approval',
  'critical',
  'scheduled',
  'in_progress',
  'pending_quote',
  'blocked',
  'completed',
  'cancelled',
];

const orderTransitions: Partial<Record<MaintenanceOrderStatus, MaintenanceOrderStatus[]>> = {
  scheduled: ['in_progress', 'pending_quote', 'blocked', 'cancelled'],
  in_progress: ['pending_quote', 'blocked', 'completed', 'cancelled'],
  pending_quote: ['scheduled', 'cancelled'],
  blocked: ['scheduled', 'in_progress', 'cancelled'],
};

const orderStatusLabels: Record<MaintenanceOrderStatus, string> = {
  pending_approval: 'Pendiente de aprobación',
  critical: 'Crítica · requiere aprobación',
  scheduled: 'Programada',
  in_progress: 'En progreso',
  pending_quote: 'Pendiente de cotización',
  blocked: 'Bloqueada',
  completed: 'Completada',
  cancelled: 'Cancelada',
};

function MaintenanceModule({ api, bimHref, pendingRequests }: { api: DashboardApi; bimHref: string; pendingRequests: number }) {
  const [anomalies, setAnomalies] = useState<TwinAnomaly[]>([]);
  const [orders, setOrders] = useState<MaintenanceOrder[]>([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [error, setError] = useState('');
  const [ordersError, setOrdersError] = useState('');
  const [formError, setFormError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [creating, setCreating] = useState(false);
  const [workingOrder, setWorkingOrder] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('iluminacion');
  const [severity, setSeverity] = useState('medium');
  const pageSize = 50;

  async function loadOrders(nextPage = page, nextStatus = statusFilter) {
    setOrdersLoading(true);
    setOrdersError('');
    const options = { page: nextPage, pageSize, ...(nextStatus ? { status: nextStatus } : {}) };
    try {
      const result = await api.maintenanceOrders(options);
      setCanManage(true);
      setOrders(result.items);
      setTotalOrders(result.total);
      setPage(nextPage);
    } catch (reason) {
      if (!(reason instanceof DashboardApiError) || reason.status !== 403) {
        setOrdersError(messageFrom(reason));
        setOrdersLoading(false);
        return;
      }
      try {
        const result = await api.maintenanceOrders({ ...options, mine: true });
        setCanManage(false);
        setOrders(result.items);
        setTotalOrders(result.total);
        setPage(nextPage);
      } catch (fallbackReason) {
        setOrdersError(messageFrom(fallbackReason));
      }
    } finally {
      setOrdersLoading(false);
    }
  }

  async function loadAnomalies() {
    setError('');
    setLoading(true);
    try {
      setAnomalies(await api.anomalies(50));
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAnomalies();
    void loadOrders(1, '');
  }, [api]);

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setFormError('');
    setActionMessage('');
    try {
      const result = await api.createMaintenanceOrder({
        title: title.trim(),
        description: description.trim(),
        category,
        severity,
      });
      setTitle('');
      setDescription('');
      setActionMessage(`Solicitud ${result.code} creada; quedó pendiente de aprobación.`);
      await loadOrders(1, statusFilter);
    } catch (reason) {
      setFormError(messageFrom(reason));
    } finally {
      setCreating(false);
    }
  }

  async function approveOrder(order: MaintenanceOrder) {
    setWorkingOrder(order.id);
    setOrdersError('');
    setActionMessage('');
    try {
      await api.approveMaintenanceOrder(order.id, order.version);
      setActionMessage(`La orden ${order.code} fue aprobada.`);
      await loadOrders(page, statusFilter);
    } catch (reason) {
      setOrdersError(messageFrom(reason));
    } finally {
      setWorkingOrder('');
    }
  }

  async function transitionOrder(order: MaintenanceOrder, status: MaintenanceOrderStatus) {
    setWorkingOrder(order.id);
    setOrdersError('');
    setActionMessage('');
    try {
      await api.transitionMaintenanceOrder(order.id, status, order.version);
      setActionMessage(`La orden ${order.code} cambió a “${orderStatusLabels[status]}”.`);
      await loadOrders(page, statusFilter);
    } catch (reason) {
      setOrdersError(messageFrom(reason));
    } finally {
      setWorkingOrder('');
    }
  }

  function filterOrders(value: string) {
    setStatusFilter(value);
    void loadOrders(1, value);
  }

  return (
    <ModuleFrame view="maintenance" bimHref={bimHref}>
      <div className="module-summary-grid maintenance-summary">
        <div><span>Anomalías abiertas consultadas</span><strong>{numberFormat.format(anomalies.length)}</strong></div>
        <div><span>Solicitudes propuestas desde BIM</span><strong>{numberFormat.format(pendingRequests)}</strong></div>
        <div><span>Órdenes en este resultado</span><strong>{numberFormat.format(totalOrders)}</strong></div>
      </div>
      <div className="module-action-banner"><div><strong>Flujo de diagnóstico y solicitud</strong><p>El visor mantiene el contexto 3D y el flujo de anomalía, diagnóstico, cadena de dependencia y propuesta de mantenimiento.</p></div><a className="button button-secondary" href={bimHref}>Abrir flujo en BIM <span aria-hidden="true">↗</span></a></div>
      {error && <ModuleError message={error} onRetry={() => void loadAnomalies()} />}
      {loading ? <div className="module-loading">Consultando incidencias…</div> : anomalies.length ? (
        <div className="maintenance-list">{anomalies.map((anomaly) => <article className="maintenance-card" key={anomaly.anomaly_id}>
          <span className={`severity-marker severity-${anomaly.severity.toLowerCase()}`} />
          <div><strong>{anomaly.node_name || anomaly.node_code || 'Activo sin nombre'} · {pretty(anomaly.metric)}</strong><p>{pretty(anomaly.severity)} · lectura {anomaly.observed_value ?? 'sin dato'} · referencia {anomaly.baseline_value ?? 'no definida'}</p><small>{showDate(anomaly.detected_at)} · {anomaly.anomaly_id}</small></div>
          <a href={bimHref}>Ver contexto</a>
        </article>)}</div>
      ) : !error ? <EmptyModule title="Sin incidencias abiertas" detail="Cuando se registren anomalías o resultados de inspección, aparecerán aquí vinculados al activo." /> : null}
      <section className="maintenance-workspace" aria-labelledby="maintenance-orders-title">
        <div className="maintenance-section-heading">
          <div><p className="eyebrow">ÓRDENES OPERATIVAS</p><h2 id="maintenance-orders-title">Solicitudes y seguimiento</h2></div>
          <label className="maintenance-filter">Estado
            <select value={statusFilter} onChange={(event) => filterOrders(event.target.value)}>
              <option value="">Todos los estados</option>
              {orderStatuses.map((status) => <option key={status} value={status}>{orderStatusLabels[status]}</option>)}
            </select>
          </label>
        </div>
        <form className="maintenance-create-form" onSubmit={(event) => void createOrder(event)}>
          <label>Título<input required maxLength={240} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ej. Fuga en zona común" /></label>
          <label>Categoría<select value={category} onChange={(event) => setCategory(event.target.value)}>
            {['iluminacion', 'electrico', 'hidrosanitario', 'areas_verdes', 'parqueaderos', 'seguridad', 'edificacion', 'ascensores', 'piscina', 'contra_incendio', 'telecomunicaciones', 'unknown'].map((value) => <option key={value} value={value}>{pretty(value)}</option>)}
          </select></label>
          <label>Severidad<select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            {['info', 'low', 'medium', 'high', 'critical'].map((value) => <option key={value} value={value}>{pretty(value)}</option>)}
          </select></label>
          <label className="maintenance-description-field">Descripción<textarea maxLength={12000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Describe el problema observado." rows={2} /></label>
          <button className="button button-primary" type="submit" disabled={creating || !title.trim()}>{creating ? 'Enviando…' : 'Crear solicitud'}</button>
        </form>
        <p className="module-note">La solicitud se registra en el ERP y no se ejecuta automáticamente. Una persona autorizada debe aprobarla antes de iniciar el trabajo.</p>
        {formError && <p className="maintenance-feedback maintenance-feedback-error" role="alert">{formError}</p>}
        {actionMessage && <p className="maintenance-feedback" role="status">{actionMessage}</p>}
        {ordersError && <ModuleError message={ordersError} onRetry={() => void loadOrders()} />}
        {ordersLoading ? <div className="module-loading">Consultando órdenes operativas…</div> : orders.length ? (
          <div className="maintenance-list">
            {orders.map((order) => {
              const isWorking = workingOrder === order.id;
              const canApprove = canManage && ['pending_approval', 'critical'].includes(order.status);
              const transitions = canManage ? orderTransitions[order.status] ?? [] : [];
              return <article className="maintenance-order-card" key={order.id}>
                <div className="maintenance-order-main">
                  <div className="maintenance-order-title">
                    <div><strong>{order.title}</strong><small>{order.code} · {pretty(order.category)} · {pretty(order.severity)}</small></div>
                    <span className={`module-state state-${order.status}`}>{orderStatusLabels[order.status]}</span>
                  </div>
                  {order.description && <p className="maintenance-order-description">{order.description}</p>}
                  <div className="maintenance-order-meta">
                    <span>Reportó: {order.reporter_name}</span>
                    <span>Creada: {showDate(order.created_at)}</span>
                    {order.vendor_name && <span>Proveedor: {order.vendor_name}</span>}
                    {order.cost_cop != null && <span>Costo: {numberFormat.format(order.cost_cop)} COP</span>}
                  </div>
                </div>
                {(canApprove || transitions.length > 0) && <div className="maintenance-order-actions">
                  {canApprove && <button className="button button-primary" type="button" disabled={isWorking} onClick={() => void approveOrder(order)}>{isWorking ? 'Guardando…' : 'Aprobar'}</button>}
                  {transitions.map((nextStatus) => <button key={nextStatus} className="button button-secondary" type="button" disabled={isWorking} onClick={() => void transitionOrder(order, nextStatus)}>{orderStatusLabels[nextStatus]}</button>)}
                </div>}
              </article>;
            })}
          </div>
        ) : !ordersError ? <EmptyModule title="No hay órdenes para mostrar" detail={canManage ? 'Crea una solicitud o espera a que se registre una incidencia.' : 'Las solicitudes que registres aparecerán aquí junto con su estado de aprobación.'} /> : null}
        <div className="module-pagination"><span>{totalOrders ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, totalOrders)} de ${totalOrders}` : 'Sin órdenes'}</span><div>
          <button type="button" disabled={ordersLoading || page <= 1} onClick={() => void loadOrders(page - 1)}>Anterior</button>
          <button type="button" disabled={ordersLoading || page * pageSize >= totalOrders} onClick={() => void loadOrders(page + 1)}>Siguiente</button>
        </div></div>
      </section>
      {canManage && <MaintenanceDirectory api={api} />}
      <p className="module-note">Las anomalías, propuestas BIM y órdenes operativas son conceptos distintos. El ERP conserva las decisiones de aprobación, cambios de estado e historial auditable.</p>
    </ModuleFrame>
  );
}

type ResidentDraft = {
  id: string | null;
  user_id: string;
  full_name: string;
  phone: string;
  active: boolean;
  unit_ids: string[];
  primary_unit_id: string;
};

type VendorDraft = {
  id: string | null;
  name: string;
  nit: string;
  categories: string[];
  status: MaintenanceVendor['status'];
  documents_valid_until: string;
  rating: string;
};

const maintenanceCategories = [
  'iluminacion', 'electrico', 'hidrosanitario', 'areas_verdes', 'parqueaderos',
  'seguridad', 'edificacion', 'ascensores', 'piscina', 'contra_incendio',
  'telecomunicaciones', 'unknown',
];

function MaintenanceDirectory({ api }: { api: DashboardApi }) {
  const [residents, setResidents] = useState<MaintenancePage<MaintenanceResident> | null>(null);
  const [vendors, setVendors] = useState<MaintenancePage<MaintenanceVendor> | null>(null);
  const [units, setUnits] = useState<MaintenancePage<MaintenanceUnit> | null>(null);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [canAdmin, setCanAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [directoryError, setDirectoryError] = useState('');
  const [residentError, setResidentError] = useState('');
  const [vendorError, setVendorError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [residentDraft, setResidentDraft] = useState<ResidentDraft | null>(null);
  const [vendorDraft, setVendorDraft] = useState<VendorDraft | null>(null);
  const [savingResident, setSavingResident] = useState(false);
  const [savingVendor, setSavingVendor] = useState(false);
  const [residentSearch, setResidentSearch] = useState('');
  const [vendorSearch, setVendorSearch] = useState('');
  const [unitSearch, setUnitSearch] = useState('');

  async function loadDirectory() {
    setLoading(true);
    setDirectoryError('');
    setCanAdmin(false);
    try {
      const [residentPage, vendorPage, unitPage] = await Promise.all([
        api.maintenanceResidents({ q: residentSearch }),
        api.maintenanceVendors({ q: vendorSearch }),
        api.maintenanceUnits({ q: unitSearch }),
      ]);
      setResidents(residentPage);
      setVendors(vendorPage);
      setUnits(unitPage);
      try {
        setUsers(await api.tenantUsers());
        setCanAdmin(true);
      } catch (reason) {
        if (reason instanceof DashboardApiError && reason.status === 403) {
          setCanAdmin(false);
        } else {
          throw reason;
        }
      }
    } catch (reason) {
      setDirectoryError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }

  async function loadResidents(page = 1, q = residentSearch) {
    setDirectoryError('');
    try {
      setResidents(await api.maintenanceResidents({ page, pageSize: 100, q }));
    } catch (reason) {
      setDirectoryError(messageFrom(reason));
    }
  }

  async function loadVendors(page = 1, q = vendorSearch) {
    setDirectoryError('');
    try {
      setVendors(await api.maintenanceVendors({ page, pageSize: 100, q }));
    } catch (reason) {
      setDirectoryError(messageFrom(reason));
    }
  }

  async function loadUnits(page = 1, q = unitSearch) {
    setDirectoryError('');
    try {
      setUnits(await api.maintenanceUnits({ page, pageSize: 100, q }));
    } catch (reason) {
      setDirectoryError(messageFrom(reason));
    }
  }

  useEffect(() => {
    void loadDirectory();
  }, [api]);

  const activeUsers = users.filter((user) => user.is_active);

  function editResident(resident: MaintenanceResident) {
    const unitIds = [...resident.unit_ids];
    setResidentDraft({
      id: resident.id,
      user_id: resident.user_id,
      full_name: resident.full_name,
      phone: resident.phone ?? '',
      active: resident.active,
      unit_ids: unitIds,
      primary_unit_id: resident.primary_unit_id ?? unitIds[0] ?? '',
    });
    setResidentError('');
  }

  function toggleResidentUnit(unitId: string, checked: boolean) {
    setResidentDraft((draft) => {
      if (!draft) return draft;
      const unitIds = checked
        ? Array.from(new Set([...draft.unit_ids, unitId]))
        : draft.unit_ids.filter((id) => id !== unitId);
      return {
        ...draft,
        unit_ids: unitIds,
        primary_unit_id: checked
          ? draft.primary_unit_id || unitId
          : draft.primary_unit_id === unitId ? unitIds[0] ?? '' : draft.primary_unit_id,
      };
    });
  }

  async function saveResident(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!residentDraft) return;
    setSavingResident(true);
    setResidentError('');
    setFeedback('');
    const payload: ResidentWrite = {
      full_name: residentDraft.full_name.trim(),
      phone: residentDraft.phone.trim() || null,
      unit_ids: residentDraft.unit_ids,
      primary_unit_id: residentDraft.primary_unit_id,
    };
    try {
      if (residentDraft.id) {
        await api.updateMaintenanceResident(residentDraft.id, { ...payload, active: residentDraft.active });
        setFeedback('Perfil de residente actualizado.');
      } else {
        await api.createMaintenanceResident({ ...payload, user_id: residentDraft.user_id });
        setFeedback('Perfil de residente creado.');
      }
      setResidentDraft(null);
      await loadDirectory();
    } catch (reason) {
      setResidentError(messageFrom(reason));
    } finally {
      setSavingResident(false);
    }
  }

  function editVendor(vendor: MaintenanceVendor) {
    setVendorDraft({
      id: vendor.id,
      name: vendor.name,
      nit: vendor.nit,
      categories: [...vendor.categories],
      status: vendor.status,
      documents_valid_until: vendor.documents_valid_until ?? '',
      rating: vendor.rating == null ? '' : String(vendor.rating),
    });
    setVendorError('');
  }

  async function saveVendor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vendorDraft) return;
    setSavingVendor(true);
    setVendorError('');
    setFeedback('');
    const parsedRating = vendorDraft.rating.trim() ? Number(vendorDraft.rating) : null;
    if (parsedRating != null && (!Number.isFinite(parsedRating) || parsedRating < 0 || parsedRating > 5)) {
      setVendorError('La calificación debe estar entre 0 y 5.');
      setSavingVendor(false);
      return;
    }
    const payload: VendorWrite = {
      name: vendorDraft.name.trim(),
      nit: vendorDraft.nit.trim(),
      categories: vendorDraft.categories,
      status: vendorDraft.status,
      documents_valid_until: vendorDraft.documents_valid_until || null,
      rating: parsedRating,
    };
    try {
      if (vendorDraft.id) {
        await api.updateMaintenanceVendor(vendorDraft.id, payload);
        setFeedback('Proveedor actualizado.');
      } else {
        await api.createMaintenanceVendor(payload);
        setFeedback('Proveedor creado.');
      }
      setVendorDraft(null);
      await loadDirectory();
    } catch (reason) {
      setVendorError(messageFrom(reason));
    } finally {
      setSavingVendor(false);
    }
  }

  return (
    <section className="maintenance-directory" aria-labelledby="maintenance-directory-title">
      <div className="maintenance-section-heading">
        <div><p className="eyebrow">DIRECTORIO ADMINISTRATIVO</p><h2 id="maintenance-directory-title">Residentes, unidades y proveedores</h2></div>
        <span className="module-state">Consulta del tenant activo</span>
      </div>
      {directoryError && <ModuleError message={directoryError} onRetry={() => void loadDirectory()} />}
      {feedback && <p className="maintenance-feedback" role="status">{feedback}</p>}
      {loading ? <div className="module-loading">Consultando directorios…</div> : (
        <div className="maintenance-directory-grid">
          <section className="maintenance-directory-panel" aria-labelledby="residents-title">
            <div className="maintenance-section-heading">
              <div><h3 id="residents-title">Residentes y asignaciones</h3><p>Los cambios de unidad mantienen el historial de ocupación en el ERP.</p></div>
              {canAdmin && <button className="button button-primary" type="button" onClick={() => {
                setResidentDraft({ id: null, user_id: activeUsers[0]?.id ?? '', full_name: '', phone: '', active: true, unit_ids: [], primary_unit_id: '' });
                setResidentError('');
              }}>Nuevo residente</button>}
            </div>
            <form className="maintenance-directory-search" onSubmit={(event) => {
              event.preventDefault();
              void loadResidents(1, residentSearch);
            }}>
              <label htmlFor="resident-search">Buscar residente, correo o unidad</label>
              <div><input id="resident-search" value={residentSearch} onChange={(event) => setResidentSearch(event.target.value)} /><button className="button button-secondary" type="submit">Buscar</button></div>
            </form>
            {canAdmin && residentDraft && <form className="maintenance-admin-form" onSubmit={(event) => void saveResident(event)}>
              <div className="maintenance-section-heading">
                <strong>{residentDraft.id ? 'Editar residente' : 'Crear residente'}</strong>
                <button type="button" className="maintenance-text-button" onClick={() => setResidentDraft(null)}>Cancelar</button>
              </div>
              {!residentDraft.id && <label>Usuario existente
                <select required value={residentDraft.user_id} onChange={(event) => setResidentDraft({ ...residentDraft, user_id: event.target.value })}>
                  <option value="">Selecciona un usuario activo</option>
                  {activeUsers.map((user) => <option key={user.id} value={user.id}>{user.email}</option>)}
                </select>
              </label>}
              <div className="maintenance-admin-fields">
                <label>Nombre completo<input required maxLength={240} value={residentDraft.full_name} onChange={(event) => setResidentDraft({ ...residentDraft, full_name: event.target.value })} /></label>
                <label>Teléfono<input maxLength={40} value={residentDraft.phone} onChange={(event) => setResidentDraft({ ...residentDraft, phone: event.target.value })} /></label>
              </div>
              {residentDraft.id && <label className="maintenance-checkbox"><input type="checkbox" checked={residentDraft.active} onChange={(event) => setResidentDraft({ ...residentDraft, active: event.target.checked })} /> Perfil activo</label>}
              <div className="maintenance-directory-search">
                <label htmlFor="unit-search">Buscar unidad o propiedad para asignar</label>
                <div><input id="unit-search" value={unitSearch} onChange={(event) => setUnitSearch(event.target.value)} /><button className="button button-secondary" type="button" onClick={() => void loadUnits(1, unitSearch)}>Buscar</button></div>
              </div>
              <div className="maintenance-unit-options">
                {(units?.items ?? []).map((unit) => <label key={unit.id} className="maintenance-checkbox">
                  <input type="checkbox" checked={residentDraft.unit_ids.includes(unit.id)} onChange={(event) => toggleResidentUnit(unit.id, event.target.checked)} />
                  <span>{unit.property_name} · {unit.code} — {unit.name}</span>
                </label>)}
                {!units?.items.length && <p className="module-note">No hay unidades para mostrar con este filtro.</p>}
              </div>
              <div className="module-pagination"><span>{units?.total ?? 0} unidades coincidentes</span><div>
                <button type="button" disabled={!units || units.page <= 1} onClick={() => void loadUnits((units?.page ?? 1) - 1)}>Anterior</button>
                <button type="button" disabled={!units || units.page * units.page_size >= units.total} onClick={() => void loadUnits((units?.page ?? 1) + 1)}>Siguiente</button>
              </div></div>
              <label>Unidad principal
                <select required value={residentDraft.primary_unit_id} onChange={(event) => setResidentDraft({ ...residentDraft, primary_unit_id: event.target.value })}>
                  <option value="">Selecciona una unidad asignada</option>
                  {residentDraft.unit_ids.map((unitId) => {
                    const unit = units?.items.find((item) => item.id === unitId);
                    return <option key={unitId} value={unitId}>{unit ? `${unit.property_name} · ${unit.code}` : unitId}</option>;
                  })}
                </select>
              </label>
              {residentError && <p className="maintenance-feedback maintenance-feedback-error" role="alert">{residentError}</p>}
              {canAdmin && !activeUsers.length && !residentDraft.id && <p className="module-note">No hay usuarios activos disponibles. Crea o activa una identidad desde la gestión de usuarios.</p>}
              <button className="button button-primary" type="submit" disabled={savingResident || !residentDraft.full_name.trim() || !residentDraft.unit_ids.length || !residentDraft.primary_unit_id || (!residentDraft.id && !residentDraft.user_id)}>
                {savingResident ? 'Guardando…' : residentDraft.id ? 'Guardar cambios' : 'Crear perfil'}
              </button>
            </form>}
            {residents?.items.length ? <div className="maintenance-directory-list">{residents.items.map((resident) => <article className="maintenance-directory-card" key={resident.id}>
              <div><strong>{resident.full_name}</strong><small>{resident.email}{resident.phone ? ` · ${resident.phone}` : ''}</small><small>{resident.property_name ?? 'Propiedad no asignada'} · {resident.unit_code ?? 'Sin unidad principal'}</small></div>
              <span className={`module-state state-${resident.active ? 'active' : 'inactive'}`}>{resident.active ? 'Activo' : 'Inactivo'}</span>
              {canAdmin && <button type="button" className="maintenance-text-button" onClick={() => editResident(resident)}>Editar</button>}
            </article>)}</div> : !directoryError && <EmptyModule title="Sin residentes registrados" detail="Los perfiles se vinculan a usuarios y unidades ya existentes en este tenant." />}
            <div className="module-pagination"><span>{residents?.total ?? 0} residentes</span><div>
              <button type="button" disabled={!residents || residents.page <= 1} onClick={() => void loadResidents((residents?.page ?? 1) - 1)}>Anterior</button>
              <button type="button" disabled={!residents || residents.page * residents.page_size >= residents.total} onClick={() => void loadResidents((residents?.page ?? 1) + 1)}>Siguiente</button>
            </div></div>
          </section>

          <section className="maintenance-directory-panel" aria-labelledby="vendors-title">
            <div className="maintenance-section-heading">
              <div><h3 id="vendors-title">Proveedores</h3><p>La vigencia documental es una fecha declarada, no una verificación documental.</p></div>
              {canAdmin && <button className="button button-primary" type="button" onClick={() => {
                setVendorDraft({ id: null, name: '', nit: '', categories: [], status: 'active', documents_valid_until: '', rating: '' });
                setVendorError('');
              }}>Nuevo proveedor</button>}
            </div>
            <form className="maintenance-directory-search" onSubmit={(event) => {
              event.preventDefault();
              void loadVendors(1, vendorSearch);
            }}>
              <label htmlFor="vendor-search">Buscar proveedor o NIT</label>
              <div><input id="vendor-search" value={vendorSearch} onChange={(event) => setVendorSearch(event.target.value)} /><button className="button button-secondary" type="submit">Buscar</button></div>
            </form>
            {canAdmin && vendorDraft && <form className="maintenance-admin-form" onSubmit={(event) => void saveVendor(event)}>
              <div className="maintenance-section-heading">
                <strong>{vendorDraft.id ? 'Editar proveedor' : 'Crear proveedor'}</strong>
                <button type="button" className="maintenance-text-button" onClick={() => setVendorDraft(null)}>Cancelar</button>
              </div>
              <div className="maintenance-admin-fields">
                <label>Razón social<input required maxLength={240} value={vendorDraft.name} onChange={(event) => setVendorDraft({ ...vendorDraft, name: event.target.value })} /></label>
                <label>NIT<input required minLength={3} maxLength={32} value={vendorDraft.nit} onChange={(event) => setVendorDraft({ ...vendorDraft, nit: event.target.value })} /></label>
              </div>
              <div className="maintenance-admin-fields">
                <label>Estado<select value={vendorDraft.status} onChange={(event) => setVendorDraft({ ...vendorDraft, status: event.target.value as MaintenanceVendor['status'] })}>
                  {(['active', 'suspended', 'inactive'] as const).map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
                </select></label>
                <label>Fecha declarada de vigencia<input type="date" value={vendorDraft.documents_valid_until} onChange={(event) => setVendorDraft({ ...vendorDraft, documents_valid_until: event.target.value })} /></label>
                <label>Calificación (0–5)<input type="number" min="0" max="5" step="0.01" value={vendorDraft.rating} onChange={(event) => setVendorDraft({ ...vendorDraft, rating: event.target.value })} /></label>
              </div>
              <fieldset className="maintenance-category-options"><legend>Categorías de servicio</legend>
                {maintenanceCategories.map((category) => <label key={category} className="maintenance-checkbox">
                  <input type="checkbox" checked={vendorDraft.categories.includes(category)} onChange={(event) => setVendorDraft({
                    ...vendorDraft,
                    categories: event.target.checked
                      ? Array.from(new Set([...vendorDraft.categories, category]))
                      : vendorDraft.categories.filter((value) => value !== category),
                  })} />
                  {pretty(category)}
                </label>)}
              </fieldset>
              {vendorError && <p className="maintenance-feedback maintenance-feedback-error" role="alert">{vendorError}</p>}
              <button className="button button-primary" type="submit" disabled={savingVendor || !vendorDraft.name.trim() || vendorDraft.nit.trim().length < 3}>
                {savingVendor ? 'Guardando…' : vendorDraft.id ? 'Guardar cambios' : 'Crear proveedor'}
              </button>
            </form>}
            {vendors?.items.length ? <div className="maintenance-directory-list">{vendors.items.map((vendor) => <article className="maintenance-directory-card" key={vendor.id}>
              <div><strong>{vendor.name}</strong><small>NIT {vendor.nit} · {vendor.categories.map(pretty).join(', ') || 'Sin categorías'}</small>
                <small>Documentos: {vendor.documents_valid_until ? `${vendor.documents_current ? 'vigencia declarada hasta' : 'fecha vencida'} ${vendor.documents_valid_until}` : 'sin fecha declarada'} · Calificación: {vendor.rating ?? 'Sin dato'}</small>
              </div>
              <span className={`module-state state-${vendor.status}`}>{pretty(vendor.status)}</span>
              {canAdmin && <button type="button" className="maintenance-text-button" onClick={() => editVendor(vendor)}>Editar</button>}
            </article>)}</div> : !directoryError && <EmptyModule title="Sin proveedores registrados" detail="Los proveedores activos podrán asociarse a órdenes desde el ERP." />}
            <div className="module-pagination"><span>{vendors?.total ?? 0} proveedores</span><div>
              <button type="button" disabled={!vendors || vendors.page <= 1} onClick={() => void loadVendors((vendors?.page ?? 1) - 1)}>Anterior</button>
              <button type="button" disabled={!vendors || vendors.page * vendors.page_size >= vendors.total} onClick={() => void loadVendors((vendors?.page ?? 1) + 1)}>Siguiente</button>
            </div></div>
          </section>
        </div>
      )}
      <p className="module-note">Las escrituras de residentes y proveedores requieren rol administrativo; la API aplica el control de acceso y el alcance del tenant en cada solicitud.</p>
    </section>
  );
}

function IntelligenceModule({ bimHref }: { bimHref: string }) {
  return (
    <ModuleFrame view="intelligence" bimHref={bimHref}>
      <div className="intelligence-grid">
        <article><span className="intelligence-number">01</span><h2>Diagnóstico con evidencia</h2><p>El flujo disponible relaciona anomalías, señales temporales y dependencias para presentar evidencia; una correlación no se declara automáticamente causa raíz.</p><span className="module-state state-fresh">Flujo disponible en BIM</span></article>
        <article><span className="intelligence-number">02</span><h2>Contexto de red y activos</h2><p>Las relaciones dependen de nodos, vínculos y relaciones presentes en el gemelo. Las redes MEP se habilitan cuando el IFC contiene asignaciones reconocibles.</p><span className="module-state state-no_data">Requiere relaciones verificadas</span></article>
        <article><span className="intelligence-number">03</span><h2>Asistencia con control humano</h2><p>Las recomendaciones deben mostrar sus fuentes, nivel de confianza y límites. Las intervenciones que cambian el estado operativo requieren aprobación explícita.</p><span className="module-state state-stale">No ejecutar automatizaciones implícitas</span></article>
      </div>
      <div className="module-action-banner"><div><strong>Continuar en el centro de mando BIM</strong><p>Consulta grafo, flujo de fallas, propiedades importadas y relaciones del IFC desde el visor existente.</p></div><a className="button button-primary" href={bimHref}>Explorar diagnóstico <span aria-hidden="true">↗</span></a></div>
    </ModuleFrame>
  );
}

export function PlatformModule({ view, api, bimHref, pendingRequests }: { view: Exclude<WorkspaceView, 'overview'>; api: DashboardApi; bimHref: string; pendingRequests: number }) {
  if (view === 'assets') return <AssetsModule api={api} bimHref={bimHref} />;
  if (view === 'signals') return <SignalsModule api={api} bimHref={bimHref} />;
  if (view === 'models') return <ModelsModule api={api} bimHref={bimHref} />;
  if (view === 'maintenance') return <MaintenanceModule api={api} bimHref={bimHref} pendingRequests={pendingRequests} />;
  return <IntelligenceModule bimHref={bimHref} />;
}
