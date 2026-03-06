import { useEffect, useRef, useState } from "react";
import AnomalyIndicator from "./components/AnomalyIndicator";
import MetricCard from "./components/MetricCard";
import SavingsCard from "./components/SavingsCard";
import WasteTable from "./components/WasteTable";
import TopServicesChart from "./charts/TopServicesChart";
import { fetchLatestReport, ReportFetchError } from "./services/api";


const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

function toUsd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return `$${Number(value || 0).toFixed(2)}`;
}

function toCount(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "N/A";
  }
  return String(value);
}

function isEmptyReport(report) {
  if (!report || typeof report !== "object") {
    return true;
  }

  const hasTopServices = Array.isArray(report.top_service_increases) && report.top_service_increases.length > 0;
  const hasWaste = Array.isArray(report.waste_resources) && report.waste_resources.length > 0;
  const hasCoreMetrics =
    report.total_daily_cost !== undefined ||
    report.seven_day_average !== undefined ||
    report.potential_savings !== undefined;

  return !hasTopServices && !hasWaste && !hasCoreMetrics;
}

export default function App() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [noReport, setNoReport] = useState(false);
  const activeRef = useRef(false);
  const [lastRefreshAt, setLastRefreshAt] = useState(null);

  const load = async (showLoading = true) => {
      try {
        if (showLoading) {
          setLoading(true);
        }
        setError("");
        setNoReport(false);
        const data = await fetchLatestReport();
        if (activeRef.current) {
          setReport(data);
          setLastRefreshAt(new Date());
        }
      } catch (err) {
        if (!activeRef.current) {
          return;
        }

        if (err instanceof ReportFetchError && err.code === "REPORT_NOT_FOUND") {
          setNoReport(true);
          setReport(null);
          setError(err.message);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load report");
        }
      } finally {
        if (activeRef.current && showLoading) {
          setLoading(false);
        }
      }
  };

  useEffect(() => {
    activeRef.current = true;

    load(true);

    const intervalId = setInterval(() => {
      if (activeRef.current) {
        load(false);
      }
    }, REFRESH_INTERVAL_MS);

    return () => {
      activeRef.current = false;
      clearInterval(intervalId);
    };
  }, []);

  const handleRetry = () => {
    load(true);
  };

  const topServices = report?.top_service_increases || [];
  const wasteResources = report?.waste_resources || [];
  const emptyReport = !loading && !noReport && !error && isEmptyReport(report);

  return (
    <main className="dashboard">
      <h1>CostSage AWS Dashboard</h1>
      <p className="subtitle">Daily cost governance and optimization summary</p>
      {!loading && lastRefreshAt && (
        <p className="muted">Auto-refresh: every 5 min • Last updated: {lastRefreshAt.toLocaleTimeString()}</p>
      )}

      {error && !noReport && <div className="error">{error}</div>}

      {loading ? (
        <div className="card">Loading latest report...</div>
      ) : noReport ? (
        <div className="notice">
          <strong>No report available yet.</strong>
          <p className="muted">Run the backend once, then refresh to load <span className="mono">latest/report.json</span>.</p>
          <button type="button" className="button" onClick={handleRetry}>Retry</button>
        </div>
      ) : error && !report ? (
        <div className="notice">
          <strong>Unable to load dashboard data.</strong>
          <p className="muted">{error}</p>
          <button type="button" className="button" onClick={handleRetry}>Retry</button>
        </div>
      ) : (
        <>
          {emptyReport && (
            <div className="notice">
              <strong>Report is available but contains no metrics yet.</strong>
              <p className="muted">Showing fallback values until the next completed run.</p>
            </div>
          )}

          <section className="grid">
            <MetricCard title="Total Cost (Yesterday)" value={toUsd(report?.total_daily_cost)} />
            <MetricCard title="7-Day Average" value={toUsd(report?.seven_day_average)} />
            <AnomalyIndicator anomaly={report?.anomaly} />
            <SavingsCard savings={report?.potential_savings} />
            <MetricCard
              title="Missing Tags Count"
              value={toCount(report?.tag_compliance?.total_missing_resources)}
            />
          </section>

          <TopServicesChart data={topServices} />
          <WasteTable rows={wasteResources} />
        </>
      )}
    </main>
  );
}
