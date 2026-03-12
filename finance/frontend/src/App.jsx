import { useEffect, useState, useCallback, useMemo } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { fetchTransactions, fetchSummary } from "./api";
import InflowOutflow from "./components/InflowOutflow";
import CategoryPieChart from "./components/CategoryPieChart";
import CumulativeChart from "./components/CumulativeChart";
import RecentTransactions from "./components/RecentTransactions";
import CategoryDrilldown from "./components/CategoryDrilldown";
import ProtectedRoute from "./components/ProtectedRoute";
import ProjectNav from "./components/ProjectNav";

const DEFAULT_EXCLUDED = new Set(["Transfer", "Credit Card Payment"]);

function StatCard({ label, value, color }) {
  return (
    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "AED",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function TypeToggle({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
        active
          ? "bg-blue-600 text-white"
          : "bg-gray-800 text-gray-500 hover:text-gray-300"
      }`}
    >
      {label}
    </button>
  );
}

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [allCategories, setAllCategories] = useState([]);
  const [activeCategories, setActiveCategories] = useState(null);
  const [drilldown, setDrilldown] = useState(null);

  const loadAllTransactions = useCallback(async () => {
    const all = [];
    let page = 1;
    while (true) {
      const batch = await fetchTransactions(page, 200);
      if (!batch) break;
      all.push(...batch);
      if (batch.length < 200) break;
      page++;
    }
    return all;
  }, []);

  const load = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([fetchSummary(), loadAllTransactions()]);
      if (!s || !t) return;
      setSummary(s);
      setTransactions(t);

      const cats = new Set();
      for (const r of s.by_category_spend || []) cats.add(r.category);
      for (const r of s.by_category_income || []) cats.add(r.category);
      for (const r of s.by_month || []) cats.add(r.category);
      for (const r of s.by_day || []) cats.add(r.category);
      for (const r of t) if (r.category) cats.add(r.category);
      const sorted = [...cats].sort();
      setAllCategories(sorted);
      setActiveCategories((prev) => {
        if (prev !== null) return prev;
        const initial = new Set(sorted);
        DEFAULT_EXCLUDED.forEach((c) => initial.delete(c));
        return initial;
      });
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, [loadAllTransactions]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, [load]);

  const toggleCategory = (cat) => {
    setActiveCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const filtered = useMemo(() => {
    if (!summary || !activeCategories)
      return { by_month: [], by_category_spend: [], by_category_income: [], by_day: [], inflow: 0, outflow: 0 };

    // Filter monthly data
    const monthMap = {};
    for (const r of summary.by_month) {
      if (!activeCategories.has(r.category)) continue;
      if (!monthMap[r.month]) monthMap[r.month] = { month: r.month, inflow: 0, outflow: 0 };
      monthMap[r.month].inflow += r.inflow;
      monthMap[r.month].outflow += r.outflow;
    }
    const by_month = Object.values(monthMap).sort((a, b) => (a.month > b.month ? 1 : -1));

    // Filter spend category data
    const by_category_spend = (summary.by_category_spend || []).filter((r) =>
      activeCategories.has(r.category)
    );

    // Filter income category data
    const by_category_income = (summary.by_category_income || []).filter((r) =>
      activeCategories.has(r.category)
    );

    // Filter daily data
    const dayMap = {};
    for (const r of summary.by_day) {
      if (!activeCategories.has(r.category)) continue;
      if (!dayMap[r.date]) dayMap[r.date] = { date: r.date, inflow: 0, outflow: 0 };
      dayMap[r.date].inflow += r.inflow;
      dayMap[r.date].outflow += r.outflow;
    }
    const by_day = Object.values(dayMap).sort((a, b) => (a.date > b.date ? 1 : -1));

    // Filtered totals
    let inflow = 0;
    let outflow = 0;
    for (const d of by_month) {
      inflow += d.inflow;
      outflow += d.outflow;
    }

    return { by_month, by_category_spend, by_category_income, by_day, inflow, outflow };
  }, [summary, activeCategories]);

  const handleLogout = () => {
    window.location.href = 'https://aldhaheri.co'
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-400 text-lg">Loading...</p>
      </div>
    );
  }

  const { inflow, outflow } = filtered;
  const net = inflow - outflow;
  const count = transactions.length;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <ProjectNav />
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Finance - AlDhaheri</h1>
            <p className="text-sm text-gray-500">Personal spending dashboard</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors"
        >
          Logout
        </button>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Inflow" value={fmt(inflow)} color="text-emerald-400" />
          <StatCard label="Total Outflow" value={fmt(outflow)} color="text-red-400" />
          <StatCard
            label="Net"
            value={fmt(net)}
            color={net >= 0 ? "text-emerald-400" : "text-red-400"}
          />
          <StatCard label="Transactions" value={count.toLocaleString()} color="text-blue-400" />
        </div>

        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-gray-500">Filter categories in charts</p>
            <div className="flex gap-2">
              <button
                onClick={() => setActiveCategories(new Set(allCategories))}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Select All
              </button>
              <span className="text-xs text-gray-700">|</span>
              <button
                onClick={() => setActiveCategories(new Set())}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Deselect All
              </button>
              <span className="text-xs text-gray-700">|</span>
              <button
                onClick={() => {
                  const inCats = new Set((summary?.by_category_income || []).map((r) => r.category));
                  setActiveCategories(inCats);
                }}
                className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                Inflow Only
              </button>
              <span className="text-xs text-gray-700">|</span>
              <button
                onClick={() => {
                  const outCats = new Set((summary?.by_category_spend || []).map((r) => r.category));
                  setActiveCategories(outCats);
                }}
                className="text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                Outflow Only
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {allCategories.map((cat) => (
              <TypeToggle
                key={cat}
                label={cat}
                active={activeCategories?.has(cat) ?? false}
                onClick={() => toggleCategory(cat)}
              />
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="text-sm font-semibold text-gray-400 mb-4">
              Monthly Inflow vs Outflow
            </h2>
            <InflowOutflow data={filtered.by_month} />
          </div>
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="text-sm font-semibold text-gray-400 mb-4">
              Spend by Category
            </h2>
            <CategoryPieChart
              data={filtered.by_category_spend}
              onCategoryClick={(cat) => setDrilldown({ category: cat, flowType: "Outflow" })}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="text-sm font-semibold text-gray-400 mb-4">
              Income by Category
            </h2>
            <CategoryPieChart
              data={filtered.by_category_income}
              onCategoryClick={(cat) => setDrilldown({ category: cat, flowType: "Inflow" })}
            />
          </div>
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="text-sm font-semibold text-gray-400 mb-4">
              Cumulative Inflow vs Outflow
            </h2>
            <CumulativeChart data={filtered.by_day} />
          </div>
        </div>

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-4">
            Recent Transactions
          </h2>
          <RecentTransactions
            transactions={transactions}
            onRefresh={load}
            allCategories={allCategories}
          />
        </div>
      </main>

      {drilldown && (
        <CategoryDrilldown
          category={drilldown.category}
          flowType={drilldown.flowType}
          transactions={transactions}
          onClose={() => setDrilldown(null)}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
