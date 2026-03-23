import { useEffect, useState, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { fetchPortfolio, addPosition, deletePosition, closePosition } from "../api";

const fmt = (n, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);

const pctClass = (v) => (v >= 0 ? "text-emerald-400" : "text-red-400");

function StatCard({ label, value, color }) {
  return (
    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function AddPositionForm({ onAdd }) {
  const [ticker, setTicker] = useState("VOO");
  const [shares, setShares] = useState("");
  const [cost, setCost] = useState("");
  const [date, setDate] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!ticker || !shares || !cost || !date) return;
    setSubmitting(true);
    try {
      const [y, m, d] = date.split("-");
      const entryDate = `${m}/${d}/${y}`;
      await onAdd({ ticker, shares: parseFloat(shares), cost_per_share: parseFloat(cost), entry_date: entryDate });
      setShares("");
      setCost("");
      setDate("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap gap-3 items-end">
      <div>
        <label className="text-xs text-gray-500 block mb-1">Ticker</label>
        <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm w-24 focus:outline-none focus:border-purple-500" />
      </div>
      <div>
        <label className="text-xs text-gray-500 block mb-1">Shares</label>
        <input type="number" step="any" value={shares} onChange={(e) => setShares(e.target.value)}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm w-24 focus:outline-none focus:border-purple-500" />
      </div>
      <div>
        <label className="text-xs text-gray-500 block mb-1">Cost/Share (USD)</label>
        <input type="number" step="any" value={cost} onChange={(e) => setCost(e.target.value)}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm w-32 focus:outline-none focus:border-purple-500" />
      </div>
      <div>
        <label className="text-xs text-gray-500 block mb-1">Entry Date</label>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-purple-500 [color-scheme:dark]" />
      </div>
      <button type="submit" disabled={submitting}
        className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
        {submitting ? "Adding..." : "Add Position"}
      </button>
    </form>
  );
}

function ClosePositionModal({ position, onClose, onConfirm }) {
  const [closePrice, setClosePrice] = useState("");
  const [closeDate, setCloseDate] = useState("");
  const [shares, setShares] = useState("");
  const [mode, setMode] = useState("full"); // "full" or "partial"
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!closePrice || !closeDate) return;
    if (mode === "partial" && (!shares || parseFloat(shares) <= 0 || parseFloat(shares) > position.shares)) return;
    setSubmitting(true);
    try {
      const [y, m, d] = closeDate.split("-");
      const data = {
        close_price: parseFloat(closePrice),
        close_date: `${m}/${d}/${y}`,
      };
      if (mode === "partial") data.shares = parseFloat(shares);
      await onConfirm(position.id, data);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-gray-100 mb-1">Close Position</h2>
        <p className="text-sm text-gray-500 mb-4">
          {position.ticker} — {position.shares} shares @ ${position.cost_per_share.toFixed(2)} (lot #{position.id})
        </p>

        <div className="flex gap-2 mb-4">
          <button onClick={() => setMode("full")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${mode === "full" ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-500"}`}>
            Full Close
          </button>
          <button onClick={() => setMode("partial")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${mode === "partial" ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-500"}`}>
            Partial Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "partial" && (
            <div>
              <label className="text-xs text-gray-500 block mb-1">Shares to Sell (max {position.shares})</label>
              <input type="number" step="any" min="0.01" max={position.shares} value={shares}
                onChange={(e) => setShares(e.target.value)}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-purple-500" />
            </div>
          )}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Sell Price (USD per share)</label>
            <input type="number" step="any" value={closePrice} onChange={(e) => setClosePrice(e.target.value)}
              className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-purple-500" />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Sell Date</label>
            <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)}
              className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:border-purple-500 [color-scheme:dark]" />
          </div>

          {closePrice && (
            <div className="bg-gray-800/50 rounded-lg p-3 text-sm">
              <p className="text-gray-400">
                Selling {mode === "partial" && shares ? shares : position.shares} shares @ ${parseFloat(closePrice || 0).toFixed(2)}
              </p>
              {(() => {
                const qty = mode === "partial" && shares ? parseFloat(shares) : position.shares;
                const proceeds = qty * parseFloat(closePrice || 0);
                const cost = qty * position.cost_per_share;
                const pnl = proceeds - cost;
                return (
                  <p className={`font-semibold mt-1 ${pctClass(pnl)}`}>
                    P&L: {fmt(pnl)} ({pnl >= 0 ? "+" : ""}{((pnl / cost) * 100).toFixed(2)}%)
                  </p>
                );
              })()}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={submitting}
              className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
              {submitting ? "Closing..." : "Confirm Close"}
            </button>
            <button type="button" onClick={onClose}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PortfolioChart({ history, showAed }) {
  if (!history || history.length === 0) return <p className="text-gray-500 text-center py-8">No data yet</p>;

  const valueKey = showAed ? "value_aed" : "value_usd";
  const costKey = showAed ? "cost_aed" : "cost_usd";
  const currency = showAed ? "AED" : "USD";

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={history}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2D2D4E" />
        <XAxis dataKey="date" stroke="#94A3B8" tick={{ fontSize: 11 }}
          tickFormatter={(d) => { const p = d.split("-"); return `${p[1]}/${p[2]}`; }} />
        <YAxis stroke="#94A3B8" tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <Tooltip contentStyle={{ background: "#1A1A2E", border: "1px solid #2D2D4E", borderRadius: 8 }}
          labelStyle={{ color: "#94A3B8" }} formatter={(v) => [fmt(v, currency), ""]} />
        <Legend />
        <Line type="monotone" dataKey={valueKey} stroke="#7C3AED" strokeWidth={2} dot={false} name="Market Value" />
        <Line type="monotone" dataKey={costKey} stroke="#94A3B8" strokeWidth={1} strokeDasharray="5 5" dot={false} name="Cost Basis" />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function Investments() {
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAed, setShowAed] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [closing, setClosing] = useState(null); // position object for close modal

  const load = useCallback(async () => {
    try {
      const data = await fetchPortfolio();
      if (data) setPortfolio(data);
    } catch (err) {
      console.error("Failed to load portfolio:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (pos) => {
    await addPosition(pos);
    setLoading(true);
    await load();
  };

  const handleDelete = async (id) => {
    setDeleting(id);
    try { await deletePosition(id); await load(); } finally { setDeleting(null); }
  };

  const handleClose = async (id, data) => {
    await closePosition(id, data);
    setClosing(null);
    setLoading(true);
    await load();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-400 text-lg">Loading portfolio...</p>
      </div>
    );
  }

  const s = portfolio?.summary || {};
  const positions = portfolio?.positions || [];
  const closedPositions = portfolio?.closed_positions || [];
  const history = portfolio?.history || [];
  const cur = showAed ? "AED" : "USD";

  return (
    <div className="space-y-6">
      {/* Currency toggle */}
      <div className="flex items-center gap-3">
        <button onClick={() => setShowAed(false)}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!showAed ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-500 hover:text-gray-300"}`}>
          USD
        </button>
        <button onClick={() => setShowAed(true)}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${showAed ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-500 hover:text-gray-300"}`}>
          AED
        </button>
        <span className="text-xs text-gray-600">Rate: 1 USD = {s.usd_aed_rate} AED</span>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Value" value={fmt(showAed ? s.total_value_aed : s.total_value_usd, cur)} color="text-purple-400" />
        <StatCard label="Total Cost" value={fmt(showAed ? s.total_cost_aed : s.total_cost_usd, cur)} color="text-gray-300" />
        <StatCard
          label="Unrealized P&L"
          value={`${fmt(showAed ? s.total_pnl_aed : s.total_pnl_usd, cur)} (${s.total_pnl_pct >= 0 ? "+" : ""}${s.total_pnl_pct}%)`}
          color={pctClass(s.total_pnl_pct)}
        />
        <StatCard
          label="Realized P&L"
          value={fmt(showAed ? s.realized_pnl_aed : s.realized_pnl_usd, cur)}
          color={pctClass(showAed ? s.realized_pnl_aed : s.realized_pnl_usd)}
        />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Return"
          value={fmt(showAed ? s.total_return_aed : s.total_return_usd, cur)}
          color={pctClass(showAed ? s.total_return_aed : s.total_return_usd)}
        />
        <StatCard
          label="Daily Change"
          value={`${s.daily_change_pct >= 0 ? "+" : ""}${s.daily_change_pct}%`}
          color={pctClass(s.daily_change_pct)}
        />
        <StatCard label="Open Shares" value={s.total_shares} color="text-blue-400" />
        <StatCard label="Closed Trades" value={closedPositions.length} color="text-gray-400" />
      </div>

      {/* Chart */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
        <h2 className="text-sm font-semibold text-gray-400 mb-4">Portfolio Value Over Time</h2>
        <PortfolioChart history={history} showAed={showAed} />
      </div>

      {/* Open positions table */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
        <h2 className="text-sm font-semibold text-gray-400 mb-4">Open Positions ({positions.length} lots)</h2>
        {positions.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No open positions.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">Ticker</th>
                  <th className="text-left py-2 px-2">Entry Date</th>
                  <th className="text-right py-2 px-2">Shares</th>
                  <th className="text-right py-2 px-2">Cost/Share</th>
                  <th className="text-right py-2 px-2">Price</th>
                  <th className="text-right py-2 px-2">Cost ({cur})</th>
                  <th className="text-right py-2 px-2">Value ({cur})</th>
                  <th className="text-right py-2 px-2">P&L ({cur})</th>
                  <th className="text-right py-2 px-2">P&L %</th>
                  <th className="text-center py-2 px-2"></th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 px-2 font-semibold text-purple-400">{p.ticker}</td>
                    <td className="py-2 px-2">{p.entry_date}</td>
                    <td className="py-2 px-2 text-right font-mono">{p.shares}</td>
                    <td className="py-2 px-2 text-right font-mono">${p.cost_per_share.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">${p.current_price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? p.cost_aed : p.cost_usd, cur)}</td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? p.value_aed : p.value_usd, cur)}</td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(p.pnl_usd)}`}>
                      {fmt(showAed ? p.pnl_aed : p.pnl_usd, cur)}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(p.pnl_pct)}`}>
                      {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%
                    </td>
                    <td className="py-2 px-2 text-center">
                      <div className="flex gap-2 justify-center">
                        <button onClick={() => setClosing(p)} title="Close position"
                          className="text-gray-600 hover:text-orange-400 transition-colors text-xs">
                          Sell
                        </button>
                        <button onClick={() => handleDelete(p.id)} disabled={deleting === p.id} title="Delete lot"
                          className="text-gray-600 hover:text-red-400 transition-colors text-xs disabled:opacity-50">
                          {deleting === p.id ? "..." : "\u2715"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
              {positions.length > 1 && (
                <tfoot>
                  <tr className="border-t border-gray-700 font-semibold">
                    <td className="py-2 px-2" colSpan={2}>Total</td>
                    <td className="py-2 px-2 text-right font-mono">{s.total_shares}</td>
                    <td className="py-2 px-2" colSpan={2}></td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? s.total_cost_aed : s.total_cost_usd, cur)}</td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? s.total_value_aed : s.total_value_usd, cur)}</td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(s.total_pnl_usd)}`}>
                      {fmt(showAed ? s.total_pnl_aed : s.total_pnl_usd, cur)}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(s.total_pnl_pct)}`}>
                      {s.total_pnl_pct >= 0 ? "+" : ""}{s.total_pnl_pct}%
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>

      {/* Closed positions / trade history */}
      {closedPositions.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="text-sm font-semibold text-gray-400 mb-4">Closed Positions ({closedPositions.length} trades)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">Ticker</th>
                  <th className="text-left py-2 px-2">Entry</th>
                  <th className="text-left py-2 px-2">Exit</th>
                  <th className="text-right py-2 px-2">Days</th>
                  <th className="text-right py-2 px-2">Shares</th>
                  <th className="text-right py-2 px-2">Buy Price</th>
                  <th className="text-right py-2 px-2">Sell Price</th>
                  <th className="text-right py-2 px-2">Cost ({cur})</th>
                  <th className="text-right py-2 px-2">Proceeds ({cur})</th>
                  <th className="text-right py-2 px-2">P&L ({cur})</th>
                  <th className="text-right py-2 px-2">Return %</th>
                </tr>
              </thead>
              <tbody>
                {closedPositions.map((p) => (
                  <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 px-2 font-semibold text-gray-400">{p.ticker}</td>
                    <td className="py-2 px-2">{p.entry_date}</td>
                    <td className="py-2 px-2">{p.close_date}</td>
                    <td className="py-2 px-2 text-right font-mono text-gray-500">{p.holding_days}d</td>
                    <td className="py-2 px-2 text-right font-mono">{p.shares}</td>
                    <td className="py-2 px-2 text-right font-mono">${p.cost_per_share.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">${p.close_price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? p.cost_aed : p.cost_usd, cur)}</td>
                    <td className="py-2 px-2 text-right font-mono">{fmt(showAed ? p.proceeds_aed : p.proceeds_usd, cur)}</td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(p.pnl_usd)}`}>
                      {fmt(showAed ? p.pnl_aed : p.pnl_usd, cur)}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(p.pnl_pct)}`}>
                      {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
              {closedPositions.length > 1 && (
                <tfoot>
                  <tr className="border-t border-gray-700 font-semibold">
                    <td className="py-2 px-2" colSpan={4}>Total Realized</td>
                    <td className="py-2 px-2 text-right font-mono">{closedPositions.reduce((s, p) => s + p.shares, 0)}</td>
                    <td colSpan={2}></td>
                    <td className="py-2 px-2 text-right font-mono">
                      {fmt(closedPositions.reduce((s, p) => s + (showAed ? p.cost_aed : p.cost_usd), 0), cur)}
                    </td>
                    <td className="py-2 px-2 text-right font-mono">
                      {fmt(closedPositions.reduce((s, p) => s + (showAed ? p.proceeds_aed : p.proceeds_usd), 0), cur)}
                    </td>
                    <td className={`py-2 px-2 text-right font-mono ${pctClass(s.realized_pnl_usd)}`}>
                      {fmt(showAed ? s.realized_pnl_aed : s.realized_pnl_usd, cur)}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}

      {/* Add position form */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
        <h2 className="text-sm font-semibold text-gray-400 mb-4">Add Position</h2>
        <AddPositionForm onAdd={handleAdd} />
      </div>

      {/* Close position modal */}
      {closing && (
        <ClosePositionModal
          position={closing}
          onClose={() => setClosing(null)}
          onConfirm={handleClose}
        />
      )}
    </div>
  );
}
