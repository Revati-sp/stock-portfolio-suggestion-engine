import StrategySelector from "./StrategySelector";

export type PortfolioBuilderState = {
  strategies: string[];
  amount: number;
  action: "generate" | "refresh" | null;
};

export type PortfolioBuilderProps = {
  state: PortfolioBuilderState;
  onChange: (next: PortfolioBuilderState) => void;
};

export default function PortfolioBuilder({ state, onChange }: PortfolioBuilderProps) {
  const update = (patch: Partial<PortfolioBuilderState>) => {
    onChange({ ...state, ...patch, action: patch.action ?? null });
  };

  return (
    <div className="w-full rounded-xl border border-slate-200 bg-slate-50 p-6 md:p-8">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-6 lg:grid-cols-12 lg:items-start">
        <div className="flex flex-col space-y-3 md:col-span-6 lg:col-span-3">
          <label
            htmlFor="investment-amount"
            className="text-[0.95rem] font-bold leading-5 text-slate-900"
          >
            Investment Amount (USD)
          </label>
          <input
            id="investment-amount"
            type="number"
            min={0}
            step={500}
            value={state.amount}
            onChange={(event) => update({ amount: Number(event.target.value) || 0 })}
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-5 text-2xl font-bold text-slate-900 shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
          <p className="text-sm font-semibold text-blue-600">Minimum is $5,000 USD</p>
        </div>

        <div className="md:col-span-6 lg:col-span-6">
          <StrategySelector
            selected={state.strategies}
            onChange={(strategies) => update({ strategies })}
          />
        </div>

        <div className="flex flex-col justify-start gap-4 md:col-span-6 lg:col-span-3">
          <button
            type="button"
            onClick={() => update({ action: "generate" })}
            className="w-full rounded-xl bg-blue-600 px-4 py-4 text-sm font-bold text-white shadow-sm transition-colors hover:bg-blue-700"
          >
            Generate Portfolio
          </button>
          <button
            type="button"
            onClick={() => update({ action: "refresh" })}
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition-colors hover:border-blue-500 hover:text-blue-600"
          >
            Update today&apos;s trend
          </button>
        </div>
      </div>
    </div>
  );
}
