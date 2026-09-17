export interface ScatterPoint {
  id: string;
  x: number;
  y: number;
  label: string;
  /** Renders the point at reduced opacity with a distinct outline — used to
   * make a thin sample size (e.g. a low trade_count) visually obvious
   * without computing or implying any statistical significance/confidence
   * score (PID-003 sec10: "without implying statistical validity"). */
  lowSample?: boolean;
}

interface ScatterPlotProps {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  /** Formats an axis tick value for display (e.g. "+12%", "340"). */
  formatX?: (v: number) => string;
  formatY?: (v: number) => string;
}

const WIDTH = 480;
const HEIGHT = 260;
const PAD_L = 46;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 34;

/** A restrained, hand-rolled SVG scatter — no charting dependency exists in
 * this project (package.json) and PID-003's own visual constraints call
 * for restraint over a "fake metric dashboard" feel, so this stays a plain
 * axes + points component rather than pulling one in. Every point plotted
 * here is a REAL discovery with both values present — callers filter out
 * missing data before this component ever sees it (never a fabricated
 * point for a null claim metric). */
export function ScatterPlot({ points, xLabel, yLabel, formatX, formatY }: ScatterPlotProps) {
  if (points.length < 2) {
    return (
      <div className="scatter-empty">
        Not enough comparable claimed data yet to plot {xLabel.toLowerCase()} vs {yLabel.toLowerCase()} — this
        needs at least two discoveries with both values present.
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(0, ...xs);
  const xMax = Math.max(...xs, xMin + 1);
  const yMin = Math.min(0, ...ys);
  const yMax = Math.max(...ys, yMin + 1);

  const px = (v: number) => PAD_L + ((v - xMin) / (xMax - xMin)) * (WIDTH - PAD_L - PAD_R);
  const py = (v: number) => HEIGHT - PAD_B - ((v - yMin) / (yMax - yMin)) * (HEIGHT - PAD_T - PAD_B);

  const xTicks = [xMin, xMin + (xMax - xMin) / 2, xMax];
  const yTicks = [yMin, yMin + (yMax - yMin) / 2, yMax];
  const fx = formatX ?? ((v: number) => v.toFixed(1));
  const fy = formatY ?? ((v: number) => v.toFixed(1));

  return (
    <svg
      className="scatter-plot"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width="100%"
      role="img"
      aria-label={`Scatter of ${yLabel} against ${xLabel}, ${points.length} discoveries plotted`}
    >
      {/* axes */}
      <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={HEIGHT - PAD_B} className="scatter-plot__axis" />
      <line x1={PAD_L} y1={HEIGHT - PAD_B} x2={WIDTH - PAD_R} y2={HEIGHT - PAD_B} className="scatter-plot__axis" />

      {yTicks.map((t, i) => (
        <g key={`y${i}`}>
          <line
            x1={PAD_L}
            x2={WIDTH - PAD_R}
            y1={py(t)}
            y2={py(t)}
            className="scatter-plot__gridline"
          />
          <text x={PAD_L - 6} y={py(t)} className="scatter-plot__tick" textAnchor="end" dominantBaseline="middle">
            {fy(t)}
          </text>
        </g>
      ))}
      {xTicks.map((t, i) => (
        <text
          key={`x${i}`}
          x={px(t)}
          y={HEIGHT - PAD_B + 16}
          className="scatter-plot__tick"
          textAnchor="middle"
        >
          {fx(t)}
        </text>
      ))}

      {points.map((p) => (
        <circle
          key={p.id}
          cx={px(p.x)}
          cy={py(p.y)}
          r={4.5}
          className={`scatter-plot__point${p.lowSample ? " scatter-plot__point--low-sample" : ""}`}
        >
          <title>
            {p.label}: {xLabel} {fx(p.x)}, {yLabel} {fy(p.y)}
            {p.lowSample ? " (low sample)" : ""}
          </title>
        </circle>
      ))}

      <text x={(WIDTH + PAD_L - PAD_R) / 2} y={HEIGHT - 4} className="scatter-plot__axis-label" textAnchor="middle">
        {xLabel}
      </text>
      <text
        x={-((HEIGHT - PAD_T - PAD_B) / 2 + PAD_T)}
        y={12}
        className="scatter-plot__axis-label"
        textAnchor="middle"
        transform="rotate(-90)"
      >
        {yLabel}
      </text>
    </svg>
  );
}
