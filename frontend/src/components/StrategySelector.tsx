import { useState } from "react";
import { BarChart3, Check, Leaf, PieChart, Shield, Tag } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Strategy = {
  id: string;
  lines: [string, string];
  Icon: LucideIcon;
  iconClassName: string;
};

const STRATEGIES: Strategy[] = [
  {
    id: "Ethical Investing",
    lines: ["Ethical", "Investing"],
    Icon: Leaf,
    iconClassName: "text-green-600",
  },
  {
    id: "Growth Investing",
    lines: ["Growth", "Investing"],
    Icon: BarChart3,
    iconClassName: "text-purple-600",
  },
  {
    id: "Index Investing",
    lines: ["Index", "Investing"],
    Icon: PieChart,
    iconClassName: "text-blue-600",
  },
  {
    id: "Quality Investing",
    lines: ["Quality", "Investing"],
    Icon: Shield,
    iconClassName: "text-orange-500",
  },
  {
    id: "Value Investing",
    lines: ["Value", "Investing"],
    Icon: Tag,
    iconClassName: "text-teal-500",
  },
];

export type StrategySelectorProps = {
  selected?: string[];
  initialSelected?: string[];
  onChange?: (selected: string[]) => void;
  embedded?: boolean;
  theme?: "light" | "dark";
};

export default function StrategySelector({
  selected: selectedProp,
  initialSelected = ["Index Investing"],
  onChange,
  embedded = false,
  theme = "light",
}: StrategySelectorProps) {
  const isDark = theme === "dark";
  const [internalSelected, setInternalSelected] = useState<string[]>(initialSelected);
  const selected = selectedProp ?? internalSelected;

  const toggleStrategy = (id: string) => {
    const next = selected.includes(id)
      ? selected.filter((item) => item !== id)
      : selected.length >= 2
        ? selected
        : [...selected, id];

    if (selectedProp === undefined) {
      setInternalSelected(next);
    }
    onChange?.(next);
  };

  return (
    <section
      className={
        embedded
          ? "w-full max-w-full min-w-0 bg-transparent"
          : "grid w-full min-w-0 grid-cols-12 items-start gap-6"
      }
    >
      <div
        className={[
          "flex flex-col justify-start space-y-4",
          embedded ? "w-full max-w-full" : "col-span-12",
        ].join(" ")}
      >
        <header>
          <h2
            className={[
              "text-[0.95rem] font-bold leading-5",
              isDark ? "text-slate-100" : "text-slate-900",
            ].join(" ")}
          >
            Select Investment Strategy
            <span
              className={[
                "ml-2 text-sm font-normal",
                isDark ? "text-slate-400" : "text-slate-500",
              ].join(" ")}
            >
              (Select one or two)
            </span>
          </h2>
        </header>

        <div
          className={[
            "flex items-center",
            embedded ? "w-full flex-nowrap justify-between gap-3" : "flex-wrap gap-4",
          ].join(" ")}
          role="group"
          aria-label="Investment strategies"
        >
          {STRATEGIES.map(({ id, lines, Icon, iconClassName }) => {
            const isSelected = selected.includes(id);

            return (
              <button
                key={id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => toggleStrategy(id)}
                className={[
                  "relative flex shrink-0 cursor-pointer flex-col items-center justify-center rounded-xl border shadow-sm transition-all duration-200",
                  isDark ? "bg-slate-800" : "bg-white",
                  "hover:-translate-y-0.5 hover:border-blue-500 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40",
                  embedded
                    ? "h-[108px] w-[104px] px-2 py-3"
                    : "h-[120px] w-[140px] px-3 py-4",
                  isSelected
                    ? isDark
                      ? "border-2 border-blue-400 bg-blue-950/35 shadow-md"
                      : "border-2 border-blue-600 bg-blue-50 shadow-md"
                    : isDark
                      ? "border border-slate-600"
                      : "border border-slate-200",
                ].join(" ")}
              >
                {isSelected ? (
                  <span
                    className={[
                      isDark
                        ? "absolute -right-1.5 -top-1.5 flex items-center justify-center rounded-full bg-blue-500 shadow-sm ring-2 ring-slate-800"
                        : "absolute -right-1.5 -top-1.5 flex items-center justify-center rounded-full bg-blue-500 shadow-sm ring-2 ring-white",
                      embedded ? "h-5 w-5" : "h-6 w-6",
                    ].join(" ")}
                  >
                    <Check
                      className={[
                        "stroke-[3] text-white",
                        embedded ? "h-3 w-3" : "h-3.5 w-3.5",
                      ].join(" ")}
                      aria-hidden
                    />
                  </span>
                ) : null}

                <Icon
                  className={[
                    iconClassName,
                    embedded ? "mb-2 h-7 w-7" : "mb-3 h-8 w-8",
                  ].join(" ")}
                  strokeWidth={1.75}
                  aria-hidden
                />

                <span
                  className={[
                    isDark
                      ? "text-center font-bold leading-tight text-slate-100"
                      : "text-center font-bold leading-tight text-slate-900",
                    embedded ? "text-[11px]" : "text-sm",
                  ].join(" ")}
                >
                  {lines[0]}
                  <br />
                  {lines[1]}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
