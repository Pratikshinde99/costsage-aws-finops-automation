export default function WasteTable({ rows }) {
  const wasteRows = Array.isArray(rows) ? rows : [];

  return (
    <div className="card section">
      <h3 className="section-title">Waste Resources</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Resource ID</th>
              <th>Created</th>
              <th>Est. Monthly Cost</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {wasteRows.length === 0 ? (
              <tr>
                <td colSpan={5} className="muted">
                  No waste resources detected.
                </td>
              </tr>
            ) : (
              wasteRows.map((item, index) => (
                <tr key={`${item.resource_id || "resource"}-${index}`}>
                  <td>{item.resource_type || "-"}</td>
                  <td>{item.resource_id || "-"}</td>
                  <td>{item.creation_date || "-"}</td>
                  <td>${Number(item.estimated_monthly_cost || 0).toFixed(2)}</td>
                  <td>{item.recommendation || "-"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
