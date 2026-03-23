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
import ChatBot from "./components/ChatBot";

const DEFAULT_EXCLUDED = new Set(["Internal Transfers", "Credit Card Payment"]);

const MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const monthLabel = (m) => {
  // m is "YYYY-MM" format like "2026-01"
  const parts = m.split("-");
  if (parts.length === 2) {
    const idx = parseInt(parts[1], 10) - 1;
    return MONTH_NAMES[idx] || m;
  }
  return m;
};

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

function FilterPills({ label, items, active, onToggle, onAll, onNone }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">{label}</p>
        <div className="flex gap-2">
          <button onClick={onAll} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">All</button>
          <span className="text-xs text-gray-700">|</span>
          <button onClick={onNone} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">None</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <TypeToggle key={item} label={item} active={active.has(item)} onClick={() => onToggle(item)} />
        ))}
      </div>
    </div>
  );
}

function FinanceSummary({ filtered, transactions, activeCategories, activeAccounts }) {
  const stats = useMemo(() => {
    if (!transactions.length) return null;

    const filteredTxns = transactions.filter(
      (t) => activeCategories?.has(t.category) && activeAccounts?.has(t.account)
    );

    // Top spend category
    const catSpend = {};
    for (const t of filteredTxns) {
      if (t.flow_type === "Outflow") {
        catSpend[t.category] = (catSpend[t.category] || 0) + t.value_aed;
      }
    }
    const topCat = Object.entries(catSpend).sort((a, b) => b[1] - a[1])[0];

    // Monthly average
    const months = new Set();
    for (const t of filteredTxns) {
      if (t.date) {
        const parts = t.date.split("/");
        if (parts.length === 3) months.add(parts[0] + "/" + parts[2]);
      }
    }
    const monthCount = Math.max(months.size, 1);
    const avgMonthlyOut = filtered.outflow / monthCount;
    const avgMonthlyIn = filtered.inflow / monthCount;

    // Top merchant by spend
    const merchSpend = {};
    for (const t of filteredTxns) {
      if (t.flow_type === "Outflow" && t.merchant) {
        merchSpend[t.merchant] = (merchSpend[t.merchant] || 0) + t.value_aed;
      }
    }
    const topMerch = Object.entries(merchSpend).sort((a, b) => b[1] - a[1])[0];

    // Savings rate
    const savingsRate = filtered.inflow > 0 ? ((filtered.inflow - filtered.outflow) / filtered.inflow) * 100 : 0;

    // Top 3 categories
    const topCats = Object.entries(catSpend).sort((a, b) => b[1] - a[1]).slice(0, 3);

    // Build analysis paragraph
    const net = filtered.inflow - filtered.outflow;
    const netWord = net >= 0 ? "surplus" : "deficit";
    let analysis = `Over the past ${monthCount} month${monthCount > 1 ? "s" : ""}, you earned ${fmt(filtered.inflow)} and spent ${fmt(filtered.outflow)}, leaving a net ${netWord} of ${fmt(Math.abs(net))}.`;

    if (savingsRate > 0) {
      analysis += ` Your savings rate is ${savingsRate.toFixed(1)}%, meaning you kept ${savingsRate.toFixed(0)} fils of every dirham earned.`;
    }

    if (topCats.length > 0) {
      const catList = topCats.map(([name, amt]) => `${name} (${fmt(amt)})`).join(", ");
      analysis += ` Your top spending categories are ${catList}.`;
    }

    if (topMerch) {
      analysis += ` The merchant you spent the most at is ${topMerch[0]} with ${fmt(topMerch[1])} total.`;
    }

    analysis += ` On average, you spend ${fmt(avgMonthlyOut)} per month and earn ${fmt(avgMonthlyIn)} per month.`;

    return { topCat, avgMonthlyOut, avgMonthlyIn, topMerch, savingsRate, monthCount, analysis };
  }, [filtered, transactions, activeCategories, activeAccounts]);

  if (!stats) return null;

  return (
    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
      <h2 className="text-sm font-semibold text-gray-400 mb-3">Summary</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
        <div className="bg-gray-800/50 rounded-lg p-3">
          <p className="text-gray-500 text-xs mb-1">Monthly Avg Spend</p>
          <p className="text-red-400 font-semibold">{fmt(stats.avgMonthlyOut)}</p>
          <p className="text-gray-600 text-xs mt-1">across {stats.monthCount} months</p>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <p className="text-gray-500 text-xs mb-1">Monthly Avg Income</p>
          <p className="text-emerald-400 font-semibold">{fmt(stats.avgMonthlyIn)}</p>
        </div>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <p className="text-gray-500 text-xs mb-1">Savings Rate</p>
          <p className={`font-semibold ${stats.savingsRate >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {stats.savingsRate.toFixed(1)}%
          </p>
        </div>
        {stats.topCat && (
          <div className="bg-gray-800/50 rounded-lg p-3">
            <p className="text-gray-500 text-xs mb-1">Top Spend Category</p>
            <p className="text-gray-200 font-semibold">{stats.topCat[0]}</p>
            <p className="text-red-400 text-xs mt-1">{fmt(stats.topCat[1])}</p>
          </div>
        )}
        {stats.topMerch && (
          <div className="bg-gray-800/50 rounded-lg p-3">
            <p className="text-gray-500 text-xs mb-1">Top Merchant</p>
            <p className="text-gray-200 font-semibold">{stats.topMerch[0]}</p>
            <p className="text-red-400 text-xs mt-1">{fmt(stats.topMerch[1])}</p>
          </div>
        )}
        <div className="bg-gray-800/50 rounded-lg p-3">
          <p className="text-gray-500 text-xs mb-1">Net Position</p>
          <p className={`font-semibold ${filtered.inflow - filtered.outflow >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {fmt(filtered.inflow - filtered.outflow)}
          </p>
        </div>
      </div>
      <div className="mt-4 bg-gray-800/30 rounded-lg p-4">
        <p className="text-sm text-gray-300 leading-relaxed">{stats.analysis}</p>
      </div>
    </div>
  );
}

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [allCategories, setAllCategories] = useState([]);
  const [activeCategories, setActiveCategories] = useState(null);
  const [allAccounts, setAllAccounts] = useState([]);
  const [activeAccounts, setActiveAccounts] = useState(null);
  const [allMonths, setAllMonths] = useState([]);
  const [activeMonths, setActiveMonths] = useState(null);
  const [allYears, setAllYears] = useState([]);
  const [activeYears, setActiveYears] = useState(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
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
      const accts = new Set();
      const mons = new Set();
      const yrs = new Set();
      for (const r of s.by_category_spend || []) cats.add(r.category);
      for (const r of s.by_category_income || []) cats.add(r.category);
      for (const r of s.by_month || []) cats.add(r.category);
      for (const r of s.by_day || []) cats.add(r.category);
      for (const r of t) {
        if (r.category) cats.add(r.category);
        if (r.account) accts.add(r.account);
        if (r.date) {
          const parts = r.date.split("/");
          if (parts.length === 3) {
            mons.add(parts[2] + "-" + parts[0]);
            yrs.add(parts[2]);
          }
        }
      }
      const sorted = [...cats].sort();
      const sortedAccts = [...accts].sort();
      const sortedMonths = [...mons].sort();
      const sortedYears = [...yrs].sort();
      setAllCategories(sorted);
      setAllAccounts(sortedAccts);
      setAllMonths(sortedMonths);
      setAllYears(sortedYears);
      setActiveCategories((prev) => {
        if (prev !== null) return prev;
        const initial = new Set(sorted);
        DEFAULT_EXCLUDED.forEach((c) => initial.delete(c));
        return initial;
      });
      setActiveAccounts((prev) => prev !== null ? prev : new Set(sortedAccts));
      setActiveMonths((prev) => prev !== null ? prev : new Set(sortedMonths));
      setActiveYears((prev) => prev !== null ? prev : new Set(sortedYears));
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

  const toggle = (setter) => (item) => {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(item)) next.delete(item);
      else next.add(item);
      return next;
    });
  };

  const toggleCategory = toggle(setActiveCategories);
  const toggleAccount = toggle(setActiveAccounts);
  const toggleMonth = toggle(setActiveMonths);
  const toggleYear = toggle(setActiveYears);

  // Helper: parse MM/DD/YYYY to comparable YYYY-MM-DD string
  const toSortable = (dateStr) => {
    const p = dateStr.split("/");
    if (p.length === 3) return `${p[2]}-${p[0].padStart(2,"0")}-${p[1].padStart(2,"0")}`;
    return dateStr;
  };

  // Helper: check if a transaction matches active account + month + year + date range filters
  const matchesFilters = useCallback((t) => {
    if (activeAccounts && !activeAccounts.has(t.account)) return false;
    if (t.date) {
      const parts = t.date.split("/");
      if (parts.length === 3) {
        if (activeYears && !activeYears.has(parts[2])) return false;
        if (activeMonths) {
          const m = parts[2] + "-" + parts[0];
          if (!activeMonths.has(m)) return false;
        }
      }
      // Date range filter (dateFrom/dateTo are YYYY-MM-DD from input[type=date])
      if (dateFrom || dateTo) {
        const sortable = toSortable(t.date);
        if (dateFrom && sortable < dateFrom) return false;
        if (dateTo && sortable > dateTo) return false;
      }
    }
    return true;
  }, [activeAccounts, activeMonths, activeYears, dateFrom, dateTo]);

  // Filtered transactions (all three filters)
  const filteredTransactions = useMemo(() => {
    return transactions.filter(
      (t) => activeCategories?.has(t.category) && matchesFilters(t)
    );
  }, [transactions, activeCategories, matchesFilters]);

  const filtered = useMemo(() => {
    if (!summary || !activeCategories)
      return { by_month: [], by_category_spend: [], by_category_income: [], by_day: [], inflow: 0, outflow: 0 };

    // Compute from filteredTransactions for accurate account+month filtering
    const monthMap = {};
    const catSpend = {};
    const catIncome = {};
    const dayMap = {};
    let inflow = 0;
    let outflow = 0;

    for (const t of filteredTransactions) {
      // By month
      if (t.date) {
        const parts = t.date.split("/");
        if (parts.length === 3) {
          const month = parts[2] + "-" + parts[0];
          if (!monthMap[month]) monthMap[month] = { month, inflow: 0, outflow: 0 };
          if (t.flow_type === "Inflow") monthMap[month].inflow += t.value_aed;
          else monthMap[month].outflow += t.value_aed;
        }
      }

      // By category
      if (t.flow_type === "Outflow") {
        catSpend[t.category] = (catSpend[t.category] || 0) + t.value_aed;
      } else {
        catIncome[t.category] = (catIncome[t.category] || 0) + t.value_aed;
      }

      // By day
      if (t.date) {
        if (!dayMap[t.date]) dayMap[t.date] = { date: t.date, inflow: 0, outflow: 0 };
        if (t.flow_type === "Inflow") dayMap[t.date].inflow += t.value_aed;
        else dayMap[t.date].outflow += t.value_aed;
      }

      // Totals
      if (t.flow_type === "Inflow") inflow += t.value_aed;
      else outflow += t.value_aed;
    }

    const by_month = Object.values(monthMap).sort((a, b) => (a.month > b.month ? 1 : -1));
    const by_category_spend = Object.entries(catSpend).map(([category, total]) => ({ category, total })).sort((a, b) => b.total - a.total);
    const by_category_income = Object.entries(catIncome).map(([category, total]) => ({ category, total })).sort((a, b) => b.total - a.total);
    const by_day = Object.values(dayMap).sort((a, b) => (a.date > b.date ? 1 : -1));

    return { by_month, by_category_spend, by_category_income, by_day, inflow, outflow };
  }, [summary, activeCategories, filteredTransactions]);

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
  const count = filteredTransactions.length;

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

        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 space-y-4">
          <FilterPills
            label="Filter by Category"
            items={allCategories}
            active={activeCategories || new Set()}
            onToggle={toggleCategory}
            onAll={() => setActiveCategories(new Set(allCategories))}
            onNone={() => setActiveCategories(new Set())}
          />
          <div className="border-t border-gray-800" />
          <FilterPills
            label="Filter by Account"
            items={allAccounts}
            active={activeAccounts || new Set()}
            onToggle={toggleAccount}
            onAll={() => setActiveAccounts(new Set(allAccounts))}
            onNone={() => setActiveAccounts(new Set())}
          />
          <div className="border-t border-gray-800" />
          <div className="flex gap-6 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <FilterPills
                label="Filter by Year"
                items={allYears}
                active={activeYears || new Set()}
                onToggle={toggleYear}
                onAll={() => setActiveYears(new Set(allYears))}
                onNone={() => setActiveYears(new Set())}
              />
            </div>
            <div className="flex-[3] min-w-[300px]">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500">Filter by Month</p>
                  <div className="flex gap-2">
                    <button onClick={() => setActiveMonths(new Set(allMonths))} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">All</button>
                    <span className="text-xs text-gray-700">|</span>
                    <button onClick={() => setActiveMonths(new Set())} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">None</button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {allMonths.map((m) => (
                    <TypeToggle key={m} label={monthLabel(m)} active={(activeMonths || new Set()).has(m)} onClick={() => toggleMonth(m)} />
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="border-t border-gray-800" />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-500">Filter by Date Range</p>
              {(dateFrom || dateTo) && (
                <button onClick={() => { setDateFrom(""); setDateTo(""); }} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">Clear</button>
              )}
            </div>
            <div className="flex gap-3 items-center">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-blue-500 [color-scheme:dark]"
              />
              <span className="text-gray-600 text-sm">to</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-blue-500 [color-scheme:dark]"
              />
            </div>
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

        <FinanceSummary
          filtered={filtered}
          transactions={transactions}
          activeCategories={activeCategories}
          activeAccounts={activeAccounts}
        />

        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-4">
            Transactions ({filteredTransactions.length})
          </h2>
          <RecentTransactions
            transactions={filteredTransactions}
            onRefresh={load}
            allCategories={allCategories}
          />
        </div>
      </main>

      {drilldown && (
        <CategoryDrilldown
          category={drilldown.category}
          flowType={drilldown.flowType}
          transactions={filteredTransactions}
          onClose={() => setDrilldown(null)}
        />
      )}

      <ChatBot onRefresh={load} />
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
