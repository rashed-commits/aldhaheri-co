import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const fmtNum = (v) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

const fmtAxis = (v) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);

function formatDate(d) {
  if (!d || d.length < 10) return d;
  const parts = d.split("/");
  if (parts.length === 3) {
    return `${parts[0]}/${parts[1]}`;
  }
  return d;
}

export default function CumulativeChart({ data }) {
  if (data.length === 0) {
    return <p className="text-gray-500 text-sm">No data yet</p>;
  }

  let cumInflow = 0;
  let cumOutflow = 0;
  const cumulative = data.map((d) => {
    cumInflow += d.inflow;
    cumOutflow += d.outflow;
    return {
      date: d.date,
      label: formatDate(d.date),
      inflow: cumInflow,
      outflow: cumOutflow,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={cumulative}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="label" stroke="#9CA3AF" tick={{ fontSize: 11 }} />
        <YAxis stroke="#9CA3AF" tick={{ fontSize: 12 }} tickFormatter={fmtAxis} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1F2937",
            border: "1px solid #374151",
            borderRadius: "8px",
          }}
          labelFormatter={(_, payload) =>
            payload?.[0]?.payload?.date || ""
          }
          formatter={(val) => fmtNum(val)}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="inflow"
          stroke="#34D399"
          name="Cumulative Inflow"
          dot={false}
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="outflow"
          stroke="#F87171"
          name="Cumulative Outflow"
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
