export default function AnomalyIndicator({ anomaly }) {
  if (!anomaly || anomaly.anomaly_detected === undefined) {
    return (
      <div className="card">
        <h3>Anomaly Indicator</h3>
        <div className="value">N/A</div>
      </div>
    );
  }

  const isAnomaly = Boolean(anomaly?.anomaly_detected);
  return (
    <div className="card">
      <h3>Anomaly Indicator</h3>
      <div className={`value ${isAnomaly ? "alert" : "ok"}`}>
        {isAnomaly ? "Detected" : "Normal"}
      </div>
    </div>
  );
}
