export default function MetricCard({ title, value }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="value">{value}</div>
    </div>
  );
}
