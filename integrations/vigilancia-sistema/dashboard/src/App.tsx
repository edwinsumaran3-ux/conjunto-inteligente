import{useEffect,useState}from"react";import{api}from"./api/client";import{Activity,AlertTriangle,Camera,Map,Shield,Cable,RadioTower,Bot}from"lucide-react";import ZonesView from"./views/ZonesView";import IncidentsView from"./views/IncidentsView";import CamerasView from"./views/CamerasView";import HealthView from"./views/HealthView";import MapView from"./views/MapView";import AgentOrchestratorView from"./views/AgentOrchestratorView";import EquipmentTopologyView from"./views/EquipmentTopologyView";import DeviceDiscoveryView from"./views/DeviceDiscoveryView";

const tabs=["zones","incidents","cameras","agents","topology","discovery","health","map"] as const;
const TAB_LABEL:Record<typeof tabs[number],string>={zones:"Zonas",incidents:"Incidentes",cameras:"Cámaras",agents:"Agentes",topology:"Topología",discovery:"Descubrimiento",health:"Salud",map:"Mapa"};
const TAB_ICON={zones:Shield,incidents:AlertTriangle,cameras:Camera,agents:Bot,topology:Cable,discovery:RadioTower,health:Activity,map:Map} as const;

export default function App(){
  const[tab,setTab]=useState<typeof tabs[number]>("zones");
  const[mode,setMode]=useState("FULL");
  const[clock,setClock]=useState("");
  useEffect(()=>{const t=setInterval(async()=>{try{await api.health();setMode("FULL")}catch{setMode("LOCAL")}},5000);return()=>clearInterval(t)},[]);
  useEffect(()=>{const t=setInterval(()=>setClock(new Date().toLocaleTimeString("es-MX")),1000);return()=>clearInterval(t)},[]);

  return (
    <div className="min-h-screen bg-transparent text-ops-ink">
      <header className="sticky top-0 z-20 flex items-center gap-4 px-5 py-3.5 border-b border-ops-line bg-ops-bg/85 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <Shield className="w-5 h-5 text-ops-accent" />
          <div className="leading-tight">
            <p className="text-sm font-semibold">Vigilancia Distribuida</p>
            <p className="text-[11px] text-ops-inkdim">centro de operaciones · edge-01</p>
          </div>
        </div>
        <div className="flex-1" />
        <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full border border-ops-line text-ops-inkdim">
          <span className={`w-1.5 h-1.5 rounded-full ${mode==="FULL"?"bg-ops-green":"bg-ops-amber"}`} /> modo {mode}
        </span>
        <span className="font-mono-ui text-xs text-ops-inkdim tabular-nums">{clock}</span>
      </header>

      <div className="flex max-w-[1360px] mx-auto">
        <nav className="hidden md:block w-[178px] shrink-0 sticky top-[57px] self-start h-[calc(100vh-57px)] px-2.5 py-5">
          {tabs.map(id=>{const Icon=TAB_ICON[id];const active=tab===id;return (
            <button key={id} onClick={()=>setTab(id)} className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] mb-0.5 text-left ${active?"bg-ops-panel2 border border-ops-line text-ops-ink":"text-ops-inkdim hover:bg-ops-linesoft hover:text-ops-ink border border-transparent"}`}>
              <Icon className="w-3.5 h-3.5" />{TAB_LABEL[id]}
            </button>
          )})}
        </nav>

        <nav className="md:hidden flex gap-1 p-2 overflow-x-auto border-b border-ops-line">
          {tabs.map(id=>{const Icon=TAB_ICON[id];return (
            <button key={id} onClick={()=>setTab(id)} className={`shrink-0 px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 ${tab===id?"bg-ops-panel2 text-ops-accent border border-ops-line":"text-ops-inkdim"}`}>
              <Icon className="w-3.5 h-3.5" />{TAB_LABEL[id]}
            </button>
          )})}
        </nav>

        <main className="flex-1 min-w-0 px-4 md:px-6 py-6">
          {tab==="zones"&&<ZonesView/>}
          {tab==="incidents"&&<IncidentsView/>}
          {tab==="cameras"&&<CamerasView/>}
          {tab==="agents"&&<AgentOrchestratorView/>}
          {tab==="topology"&&<EquipmentTopologyView/>}
          {tab==="discovery"&&<DeviceDiscoveryView/>}
          {tab==="health"&&<HealthView/>}
          {tab==="map"&&<MapView/>}
        </main>
      </div>
    </div>
  );
}
