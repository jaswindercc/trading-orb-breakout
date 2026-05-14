export default function KpiCard({ label, value, cls }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`value ${cls || ''}`}>{value}</div>
    </div>
  )
}
