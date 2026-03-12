import { useMemo } from "react";

const fmtAmt = (v) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

export default function CategoryDrilldown({ category, flowType, transactions, onClose }) {
  const filtered = useMemo(
    () => transactions.filter((t) => t.category === category && t.flow_type === flowType),
    [transactions, category, flowType]
  );

  const total = useMemo(() => filtered.reduce((s, t) => s + t.value_aed, 0), [filtered]);

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-3xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-bold text-gray-100">{category}</h2>
            <p className="text-sm text-gray-500">
              {flowType === "Inflow" ? "Income" : "Spend"} — {filtered.length} transactions — Total: AED {fmtAmt(total)}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-xl px-2"
          >
            {"\u2715"}
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-4">
          {filtered.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No transactions found</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left py-2 px-2">Date</th>
                  <th className="text-left py-2 px-2">Merchant</th>
                  <th className="text-left py-2 px-2">Account</th>
                  <th className="text-right py-2 px-2">Amount (AED)</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-2 px-2">{t.date}</td>
                    <td className="py-2 px-2">{t.merchant || "\u2014"}</td>
                    <td className="py-2 px-2 font-mono text-xs">{t.account}</td>
                    <td
                      className={`py-2 px-2 text-right font-mono ${
                        t.flow_type === "Inflow" ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {t.flow_type === "Inflow" ? "+" : "-"}
                      {fmtAmt(t.value_aed)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
