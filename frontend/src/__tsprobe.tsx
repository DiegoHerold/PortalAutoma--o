import { useState } from "react";
import { cn } from "./lib/utils";
export function Probe() {
  const [x, setX] = useState(0);
  return <div className={cn("a", "b")} onClick={() => setX(x + 1)}>{x}</div>;
}
