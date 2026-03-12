import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatMonth(ym) {
  if (!ym || !ym.includes("-")) return ym;
  const parts = ym.split("-");
  const idx = parseInt(parts[1], 10) - 1;
  return MONTH_NAMES[idx] || ym;
}

const fmtNum = (v) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

const fmtAxis = (v) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);

export default function InflowOutflow({ data }) {
  const last6 = data.slice(-6).map((d) => ({ ...d, label: formatMonth(d.month) }));

  if (last6.length === 0) {
    return <p className="text-gray-500 text-sm">No data yet</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={last6}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="label" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
        <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} tickFormatter={fmtAxis} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1F2937",
            border: "1px solid #374151",
            borderRadius: "8px",
          }}
          formatter={(val) => fmtNum(val)}
        />
        <Legend />
        <Bar dataKey="inflow" fill="#34D399" name="Inflow" radius={[4, 4, 0, 0]} />
        <Bar dataKey="outflow" fill="#F87171" name="Outflow" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
