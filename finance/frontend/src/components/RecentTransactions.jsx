import { useState, useMemo, useRef, useEffect } from "react";
import { deleteTransaction, updateTransaction } from "../api";

const DEFAULT_CATEGORIES = [
  "Food & Dining",
  "Shopping",
  "Transport",
  "Utilities",
  "Healthcare",
  "Education",
  "Entertainment",
  "Travel",
  "Real Estate",
  "Salary",
  "Transfer",
  "ATM Cash",
  "Credit Card Payment",
  "Unknown",
  "Other",
];

const fmtAmt = (v) =>
  new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);

const PAGE_SIZE = 25;

function SortHeader({ label, field, sortField, sortDir, onSort, align }) {
  const active = sortField === field;
  const arrow = active ? (sortDir === "asc" ? " \u25B2" : " \u25BC") : "";
  return (
    <th
      className={`py-2 px-2 cursor-pointer select-none hover:text-gray-300 transition-colors ${
        align === "right" ? "text-right" : "text-left"
      }`}
      onClick={() => onSort(field)}
    >
      {label}
      <span className="text-blue-400 text-xs">{arrow}</span>
    </th>
  );
}

export default function RecentTransactions({ transactions, onRefresh, allCategories }) {
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [sortField, setSortField] = useState(null);
  const [sortDir, setSortDir] = useState("desc");
  const [localPage, setLocalPage] = useState(1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestRef = useRef(null);

  const categoryList = useMemo(() => {
    const merged = new Set([...DEFAULT_CATEGORIES, ...(allCategories || [])]);
    return [...merged].sort();
  }, [allCategories]);

  const suggestions = useMemo(() => {
    if (!editValue || !showSuggestions) return [];
    const q = editValue.toLowerCase();
    return categoryList.filter((c) => c.toLowerCase().includes(q));
  }, [editValue, showSuggestions, categoryList]);

  useEffect(() => {
    const handleClick = (e) => {
      if (suggestRef.current && !suggestRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
    setLocalPage(1);
  };

  const filtered = useMemo(() => {
    let rows = transactions;
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (t) =>
          (t.merchant && t.merchant.toLowerCase().includes(q)) ||
          (t.category && t.category.toLowerCase().includes(q)) ||
          (t.account && t.account.toLowerCase().includes(q)) ||
          (t.transaction_type && t.transaction_type.toLowerCase().includes(q))
      );
    }
    if (sortField) {
      rows = [...rows].sort((a, b) => {
        let va = a[sortField];
        let vb = b[sortField];
        if (sortField === "value_aed") {
          va = (a.flow_type === "Inflow" ? 1 : -1) * a.value_aed;
          vb = (b.flow_type === "Inflow" ? 1 : -1) * b.value_aed;
        }
        if (va == null) va = "";
        if (vb == null) vb = "";
        if (typeof va === "number" && typeof vb === "number") {
          return sortDir === "asc" ? va - vb : vb - va;
        }
        const sa = String(va).toLowerCase();
        const sb = String(vb).toLowerCase();
        return sortDir === "asc" ? sa.localeCompare(sb) : sb.localeCompare(sa);
      });
    }
    return rows;
  }, [transactions, search, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paged = filtered.slice((localPage - 1) * PAGE_SIZE, localPage * PAGE_SIZE);

  const startEdit = (id, field, value) => {
    setEditing({ id, field });
    setEditValue(value || "");
  };

  const cancelEdit = () => {
    setEditing(null);
    setEditValue("");
  };

  const confirmEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await updateTransaction(editing.id, { [editing.field]: editValue || null });
      setSavedId(editing.id);
      setTimeout(() => setSavedId(null), 1500);
      setEditing(null);
      setEditValue("");
      onRefresh();
    } catch (err) {
      console.error("Update failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteTransaction(id);
      setDeletingId(null);
      onRefresh();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const renderMerchantCell = (t) => {
    if (editing?.id === t.id && editing?.field === "merchant") {
      return (
        <td className="py-2 px-2">
          <div className="flex items-center gap-1">
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmEdit();
                if (e.key === "Escape") cancelEdit();
              }}
              className="w-28 px-2 py-1 bg-gray-800 border border-blue-500 rounded text-gray-200 text-sm focus:outline-none"
              autoFocus
            />
            <button onClick={confirmEdit} disabled={saving} className="text-emerald-400 hover:text-emerald-300 text-xs px-1">
              {saving ? "..." : "\u2713"}
            </button>
            <button onClick={cancelEdit} className="text-gray-500 hover:text-gray-300 text-xs px-1">
              {"\u2715"}
            </button>
          </div>
        </td>
      );
    }
    return (
      <td className="py-2 px-2 cursor-pointer hover:text-blue-400 transition-colors" onClick={() => startEdit(t.id, "merchant", t.merchant)}>
        {t.merchant || "\u2014"}
        {savedId === t.id && <span className="ml-1 text-emerald-400 text-xs">{"\u2713"}</span>}
      </td>
    );
  };

  const renderCategoryCell = (t) => {
    if (editing?.id === t.id && editing?.field === "category") {
      return (
        <td className="py-2 px-2">
          <div className="flex items-center gap-1 relative" ref={suggestRef}>
            <div className="relative">
              <input
                type="text"
                value={editValue}
                onChange={(e) => { setEditValue(e.target.value); setShowSuggestions(true); }}
                onFocus={() => setShowSuggestions(true)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") { setShowSuggestions(false); confirmEdit(); }
                  if (e.key === "Escape") cancelEdit();
                }}
                className="w-40 px-2 py-1 bg-gray-800 border border-blue-500 rounded text-gray-200 text-sm focus:outline-none"
                placeholder="Type category..."
                autoFocus
              />
              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-50 top-full left-0 mt-1 w-48 max-h-40 overflow-y-auto bg-gray-800 border border-gray-600 rounded shadow-lg">
                  {suggestions.map((c) => (
                    <button
                      key={c}
                      className="w-full text-left px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700 transition-colors"
                      onMouseDown={(e) => { e.preventDefault(); setEditValue(c); setShowSuggestions(false); }}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button onClick={() => { setShowSuggestions(false); confirmEdit(); }} disabled={saving} className="text-emerald-400 hover:text-emerald-300 text-xs px-1">
              {saving ? "..." : "\u2713"}
            </button>
            <button onClick={cancelEdit} className="text-gray-500 hover:text-gray-300 text-xs px-1">
              {"\u2715"}
            </button>
          </div>
        </td>
      );
    }
    return (
      <td className="py-2 px-2 cursor-pointer hover:text-blue-400 transition-colors" onClick={() => startEdit(t.id, "category", t.category)}>
        {t.category}
        {savedId === t.id && <span className="ml-1 text-emerald-400 text-xs">{"\u2713"}</span>}
      </td>
    );
  };

  const renderDeleteCell = (t) => {
    if (deletingId === t.id) {
      return (
        <td className="py-2 px-2">
          <div className="flex items-center gap-1">
            <button onClick={() => handleDelete(t.id)} className="px-2 py-0.5 bg-red-900/50 text-red-400 hover:bg-red-800/50 rounded text-xs">
              Confirm
            </button>
            <button onClick={() => setDeletingId(null)} className="px-2 py-0.5 text-gray-500 hover:text-gray-300 text-xs">
              Cancel
            </button>
          </div>
        </td>
      );
    }
    return (
      <td className="py-2 px-2 text-center">
        <button onClick={() => setDeletingId(t.id)} className="text-gray-600 hover:text-red-400 text-xs" title="Delete">
          {"\u2715"}
        </button>
      </td>
    );
  };

  return (
    <div>
      <input
        type="text"
        placeholder="Search by merchant, category, account, type..."
        value={search}
        onChange={(e) => { setSearch(e.target.value); setLocalPage(1); }}
        className="w-full mb-4 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
      />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <SortHeader label="Date" field="date" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
              <SortHeader label="Time" field="time" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
              <SortHeader label="Account" field="account" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
              <SortHeader label="Merchant" field="merchant" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
              <SortHeader label="Category" field="category" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
              <SortHeader label="Amount" field="value_aed" sortField={sortField} sortDir={sortDir} onSort={handleSort} align="right" />
              <th className="text-center py-2 px-2"></th>
            </tr>
          </thead>
          <tbody>
            {paged.map((t) => (
              <tr
                key={t.id}
                className={`border-b border-gray-800/50 hover:bg-gray-800/30 ${deletingId === t.id ? "bg-red-950/20" : ""}`}
              >
                <td className="py-2 px-2">{t.date}</td>
                <td className="py-2 px-2">{t.time}</td>
                <td className="py-2 px-2 font-mono text-xs">{t.account}</td>
                {renderMerchantCell(t)}
                {renderCategoryCell(t)}
                <td className={`py-2 px-2 text-right font-mono ${t.flow_type === "Inflow" ? "text-emerald-400" : "text-red-400"}`}>
                  {t.flow_type === "Inflow" ? "+" : "-"}
                  {fmtAmt(t.value_aed)}
                </td>
                {renderDeleteCell(t)}
              </tr>
            ))}
            {paged.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-600">
                  No transactions found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-4">
        <p className="text-xs text-gray-600">
          All amounts shown in AED — Showing {filtered.length} transactions
        </p>
        {totalPages > 1 && (
          <div className="flex items-center gap-3">
            <button
              onClick={() => setLocalPage((p) => p - 1)}
              disabled={localPage <= 1}
              className="px-3 py-1 text-sm rounded border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {localPage} of {totalPages}
            </span>
            <button
              onClick={() => setLocalPage((p) => p + 1)}
              disabled={localPage >= totalPages}
              className="px-3 py-1 text-sm rounded border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
