import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function TopServicesChart({ data }) {
  const chartData = (Array.isArray(data) ? data : []).map((item) => ({
    name: item.service,
    increase: Number(item.increase || 0),
  }));

  return (
    <div className="card section" style={{ height: 340 }}>
      <h3 className="section-title">Top Service Cost Increases</h3>
      {chartData.length === 0 ? (
        <p className="muted">No service increases detected.</p>
      ) : (
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={chartData} margin={{ top: 10, right: 8, left: 8, bottom: 24 }}>
            <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-20} textAnchor="end" interval={0} height={60} stroke="#cbd5e1" />
            <YAxis stroke="#cbd5e1" />
            <Tooltip />
            <Bar dataKey="increase" fill="#60a5fa" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
