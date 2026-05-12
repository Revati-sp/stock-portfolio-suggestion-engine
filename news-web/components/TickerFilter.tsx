type TickerFilterProps = {
  tickers: string[];
  selectedTicker: string | null;
  onSelect: (ticker: string | null) => void;
};

export default function TickerFilter({
  tickers,
  selectedTicker,
  onSelect,
}: TickerFilterProps) {
  return (
    <div className="flex flex-wrap gap-3">
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={[
          "rounded-full px-4 py-2 text-sm font-semibold transition",
          selectedTicker === null
            ? "bg-blue-600 text-white shadow-sm"
            : "bg-slate-100 text-slate-700 hover:bg-blue-100",
        ].join(" ")}
      >
        All
      </button>
      {tickers.map((ticker) => {
        const active = selectedTicker === ticker;
        return (
          <button
            key={ticker}
            type="button"
            onClick={() => onSelect(ticker)}
            className={[
              "rounded-full px-4 py-2 text-sm font-semibold transition",
              active
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-slate-100 text-slate-700 hover:bg-blue-100",
            ].join(" ")}
          >
            {ticker}
          </button>
        );
      })}
    </div>
  );
}
