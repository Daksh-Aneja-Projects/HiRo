// Executive Dashboard — fully live, real-data. No placeholders, no static numbers.
// KPIs, telemetry strip, and charts are all wired to real backend endpoints and
// animate in real time (count-up, rAF meters, live sparkline).
import React, { useEffect, useMemo, useRef, useState, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { theme as tokens } from '../theme';
import DataCard from '../components/DataCard';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import BarChartWidget from '../components/charts/BarChartWidget';
import { CountUp, LiveMeter, Sparkline } from '../components/live/LivePrimitives';
import {
  getAdvancedAnalytics, getAnalyticsCharts, getTeamPerformanceTrend,
  getCurrentMetrics, getOrchestratorDashboardData,
} from '../config/api';
import { AlertTriangle, ShieldCheck, Activity, Cpu, Users, TrendingUp } from 'lucide-react';

// Parse numbers that may arrive as percent-strings ("60.6%") or plain numbers.
const num = (v, d = 0) => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : d;
  if (typeof v === 'string') {
    const n = parseFloat(v.replace(/[^0-9.\-]/g, ''));
    return Number.isFinite(n) ? n : d;
  }
  return d;
};

// One KPI tile: count-up value + trailing sparkline of the same signal.
const Kpi = memo(({ label, value, decimals = 0, suffix = '', prefix = '', color, Icon, spark }) => (
  <DataCard title={label} color={color}
    value={<CountUp value={value} decimals={decimals} suffix={suffix} prefix={prefix} />}
    icon={<Icon size={22} color={color} />}
    footer={spark !== undefined ? <Sparkline value={spark} color={color} width={150} height={30} /> : undefined} />
));
Kpi.displayName = 'Kpi';

export const Dashboard = memo(() => {
  const { user } = useAuth();
  const userName = user?.full_name || user?.username || 'there';

  const [metrics, setMetrics] = useState(null);
  const [charts, setCharts] = useState({ headcount_by_department: [], attrition_by_department: [] });
  const [trend, setTrend] = useState([]);
  const [orch, setOrch] = useState(null);
  const [live, setLive] = useState({ cpu_load: 0, memory_load: 0, machine_load: 0 });
  const [accessError, setAccessError] = useState(false);
  const pollRef = useRef(null);

  // One-time real fetches for the heavier aggregates.
  useEffect(() => {
    let alive = true;
    getAdvancedAnalytics()
      .then((r) => alive && setMetrics(r.data))
      .catch((e) => { if (e?.response?.status === 403) setAccessError(true); });
    getAnalyticsCharts().then((r) => alive && r?.data && setCharts(r.data)).catch(() => {});
    getTeamPerformanceTrend().then((r) => alive && Array.isArray(r.data) && setTrend(r.data)).catch(() => {});
    getOrchestratorDashboardData().then((r) => alive && setOrch(r.data)).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Live telemetry poll (real psutil-backed metrics) every 3s.
  useEffect(() => {
    let alive = true;
    const tick = () => getCurrentMetrics()
      .then((r) => alive && r?.data && setLive(r.data))
      .catch(() => {});
    tick();
    pollRef.current = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(pollRef.current); };
  }, []);

  const attritionPct = useMemo(() => {
    const raw = metrics?.attrition_risk;
    const n = num(raw);
    return n <= 1 ? n * 100 : n; // accept 0..1 or 0..100
  }, [metrics]);

  const headcount = num(metrics?.headcount);

  return (
    <div style={s.container} className="portal-container">
      <header style={s.header}>
        <h1 style={s.h1}>Welcome back, {userName}</h1>
        <p style={s.sub}>Live operational overview across the workforce and the orchestration layer.</p>
      </header>

      {accessError ? (
        <div style={s.notice}>
          Your role does not have access to executive analytics. Open your portal from the sidebar
          for the views assigned to you.
        </div>
      ) : (
        <>
          {/* KPI row — all real, all animated */}
          <section style={s.kpiRow}>
            <Kpi label="Composite workforce health" value={num(metrics?.value ?? metrics?.ml_score)} decimals={1}
              color={tokens.color?.['accent-primary']} Icon={TrendingUp} spark={num(metrics?.value ?? metrics?.ml_score)} />
            <Kpi label="Headcount" value={headcount}
              color={tokens.color?.['accent-2']} Icon={Users} />
            <Kpi label="Attrition risk" value={attritionPct} decimals={1} suffix="%"
              color={attritionPct > 40 ? tokens.color?.danger : tokens.color?.warning} Icon={AlertTriangle} spark={attritionPct} />
            <Kpi label="Active agents" value={num(orch?.agents)}
              color={tokens.color?.success} Icon={ShieldCheck} />
          </section>

          {/* Live telemetry strip */}
          <section style={s.telemetry}>
            <div style={s.telemetryHead}>
              <span style={s.telemetryTitle}><Activity size={15} /> Orchestration telemetry</span>
              <span style={{ ...s.badge, color: orch?.system_health === 'GREEN' ? tokens.color?.success : tokens.color?.warning }}>
                {orch?.system_health || 'LIVE'}
              </span>
            </div>
            <div style={s.meters}>
              <LiveMeter pct={num(live.cpu_load)} label="CPU load" color={tokens.color?.['accent-primary']} />
              <LiveMeter pct={num(live.memory_load)} label="Memory" color={tokens.color?.['accent-2']} />
              <LiveMeter pct={num(live.memory_load)} label="Memory in use" color={tokens.color?.success} />
            </div>
            <div style={s.spark}>
              <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}><Cpu size={13} /> live load</span>
              <Sparkline value={num(live.cpu_load)} width={220} height={34} color={tokens.color?.['accent-primary']} />
            </div>
          </section>

          {/* Live charts from the real employee UDM */}
          <section style={s.chartRow}>
            <DataCard title="Workforce performance trend" isChart minHeight="300px">
              <AreaChartWidget data={trend} minHeight="260px" color={tokens.color?.['accent-primary']} />
            </DataCard>
            <DataCard title="Headcount by department" isChart minHeight="300px">
              <BarChartWidget data={charts.headcount_by_department} minHeight="260px" color={tokens.color?.['accent-2']} />
            </DataCard>
          </section>

          <section style={s.chartRow}>
            <DataCard title="Attrition risk by department" isChart minHeight="300px">
              <BarChartWidget data={charts.attrition_by_department} minHeight="260px" color={tokens.color?.danger} />
            </DataCard>
            <DataCard title="System integrity" isChart minHeight="300px">
              <div style={s.integrity}>
                <LiveMeter pct={num(orch?.metrics?.cpu)} label="Compute headroom" color={tokens.color?.['accent-primary']} />
                <LiveMeter pct={num(orch?.metrics?.memory)} label="Memory headroom" color={tokens.color?.['accent-2']} />
                <div style={{ display: 'flex', gap: 24, marginTop: 8 }}>
                  <div><div style={s.miniLabel}>Active tasks</div><div style={s.miniVal}><CountUp value={num(orch?.active_tasks)} /></div></div>
                  <div><div style={s.miniLabel}>Message bus</div><div style={{ ...s.miniVal, color: orch?.message_bus_connected ? tokens.color?.success : tokens.color?.danger }}>
                    {orch?.message_bus_connected ? 'Connected' : 'Offline'}</div></div>
                </div>
              </div>
            </DataCard>
          </section>
        </>
      )}
    </div>
  );
});
Dashboard.displayName = 'Dashboard';

const s = {
  container: { display: 'flex', flexDirection: 'column', gap: 20, minHeight: '100%' },
  header: { marginBottom: 2 },
  h1: { fontSize: '1.6rem', fontWeight: 640, letterSpacing: '-0.022em', margin: 0, color: 'var(--text-primary)' },
  sub: { color: 'var(--text-secondary)', margin: '4px 0 0', fontSize: 13.5 },
  notice: { padding: 20, borderRadius: 12, background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' },
  kpiRow: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 },
  telemetry: { background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 12, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 },
  telemetryHead: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  telemetryTitle: { display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' },
  badge: { fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', padding: '3px 9px', borderRadius: 999, background: 'rgba(255,255,255,0.05)' },
  meters: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 22 },
  spark: { display: 'flex', alignItems: 'center', gap: 12, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 },
  chartRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  integrity: { display: 'flex', flexDirection: 'column', gap: 16, padding: '8px 4px', justifyContent: 'center', height: '100%' },
  miniLabel: { fontSize: 11.5, color: 'var(--text-tertiary)' },
  miniVal: { fontSize: 20, fontWeight: 640, color: 'var(--text-primary)', marginTop: 2 },
};

export default Dashboard;
