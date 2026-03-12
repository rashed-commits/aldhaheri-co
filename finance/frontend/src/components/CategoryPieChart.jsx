import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";

const COLORS = [
  "#34D399", "#F87171", "#60A5FA", "#FBBF24",
  "#A78BFA", "#F472B6", "#2DD4BF", "#FB923C",
];

const fmtNum = (v) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

export default function CategoryPieChart({ data, onCategoryClick }) {
  const top8 = data.slice(0, 8);

  if (top8.length === 0) {
    return <p className="text-gray-500 text-sm">No data yet</p>;
  }

  const handleClick = (entry) => {
    if (onCategoryClick) onCategoryClick(entry.category);
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={top8}
          dataKey="total"
          nameKey="category"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ category }) => category}
          labelLine={{ stroke: "#6B7280" }}
          onClick={handleClick}
          cursor="pointer"
        >
          {top8.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "#1F2937",
            border: "1px solid #374151",
            borderRadius: "8px",
          }}
          formatter={(val) => `AED ${fmtNum(val)}`}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
