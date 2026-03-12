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

export default function AccountBreakdown({ data }) {
  if (data.length === 0) {
    return <p className="text-gray-500 text-sm">No data yet</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis type="number" stroke="#9CA3AF" tick={{ fontSize: 12 }} />
        <YAxis
          dataKey="account"
          type="category"
          stroke="#9CA3AF"
          tick={{ fontSize: 12 }}
          width={120}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1F2937",
            border: "1px solid #374151",
            borderRadius: "8px",
          }}
        />
        <Legend />
        <Bar dataKey="inflow" fill="#34D399" name="Inflow" radius={[0, 4, 4, 0]} />
        <Bar dataKey="outflow" fill="#F87171" name="Outflow" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
