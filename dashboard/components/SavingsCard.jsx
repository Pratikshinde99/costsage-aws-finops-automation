export default function SavingsCard({ savings }) {
  return (
    <div className="card">
      <h3>Estimated Savings</h3>
      <div className="value">${Number(savings || 0).toFixed(2)}/month</div>
    </div>
  );
}
