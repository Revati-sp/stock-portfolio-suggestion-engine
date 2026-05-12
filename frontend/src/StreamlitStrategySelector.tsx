import { useEffect, useState } from "react";
import {
  ComponentProps,
  Streamlit,
  withStreamlitConnection,
} from "streamlit-component-lib";
import StrategySelector from "./components/StrategySelector";

const FRAME_HEIGHT = 160;

function StrategySelectorBridge({ args }: ComponentProps) {
  const defaultSelected = Array.isArray(args.default)
    ? (args.default as string[])
    : ["Index Investing"];
  const [selected, setSelected] = useState<string[]>(defaultSelected);

  useEffect(() => {
    if (Array.isArray(args.default)) {
      setSelected(args.default as string[]);
    }
  }, [args.default]);

  useEffect(() => {
    Streamlit.setComponentValue(selected);
    Streamlit.setFrameHeight(FRAME_HEIGHT);
  }, [selected]);

  const theme = args.theme === "dark" ? "dark" : "light";

  return (
    <StrategySelector
      embedded
      theme={theme}
      selected={selected}
      onChange={setSelected}
    />
  );
}

export default withStreamlitConnection(StrategySelectorBridge);
