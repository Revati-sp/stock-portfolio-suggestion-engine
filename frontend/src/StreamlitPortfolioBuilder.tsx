import { useEffect, useState } from "react";
import {
  ComponentProps,
  Streamlit,
  withStreamlitConnection,
} from "streamlit-component-lib";
import PortfolioBuilder, {
  type PortfolioBuilderState,
} from "./components/PortfolioBuilder";

const FRAME_HEIGHT = 300;

function normalizeState(raw: unknown): PortfolioBuilderState {
  const value = (raw ?? {}) as Partial<PortfolioBuilderState>;
  return {
    strategies: Array.isArray(value.strategies)
      ? value.strategies
      : ["Index Investing"],
    amount: typeof value.amount === "number" ? value.amount : 10_000,
    action: value.action === "generate" || value.action === "refresh" ? value.action : null,
  };
}

function PortfolioBuilderBridge({ args }: ComponentProps) {
  const [state, setState] = useState<PortfolioBuilderState>(() => normalizeState(args.default));

  useEffect(() => {
    setState(normalizeState(args.default));
  }, [args.default]);

  useEffect(() => {
    Streamlit.setComponentValue(state);
    Streamlit.setFrameHeight(FRAME_HEIGHT);
  }, [state]);

  return (
    <PortfolioBuilder
      state={state}
      onChange={(next) => {
        setState(next);
        Streamlit.setComponentValue(next);
        Streamlit.setFrameHeight(FRAME_HEIGHT);
      }}
    />
  );
}

export default withStreamlitConnection(PortfolioBuilderBridge);
