import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

/* ── Premium dark theme for all Plotly charts ── */
const PREMIUM_THEME = {
  colorway: [
    '#63d396', '#4ac2dc', '#a78bfa', '#f59e0b', '#ff5f6d',
    '#6ee7b7', '#67e8f9', '#c4b5fd', '#fbbf24', '#fda4af',
  ],
  font: {
    family: "'Inter', -apple-system, sans-serif",
    color: 'rgba(234,237,243,0.7)',
    size: 12,
  },
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  xaxis: {
    gridcolor: 'rgba(255,255,255,0.04)',
    zerolinecolor: 'rgba(255,255,255,0.06)',
    linecolor: 'rgba(255,255,255,0.06)',
    tickfont: { color: 'rgba(234,237,243,0.5)', size: 11 },
    title: { font: { color: 'rgba(234,237,243,0.6)', size: 12 } },
  },
  yaxis: {
    gridcolor: 'rgba(255,255,255,0.04)',
    zerolinecolor: 'rgba(255,255,255,0.06)',
    linecolor: 'rgba(255,255,255,0.06)',
    tickfont: { color: 'rgba(234,237,243,0.5)', size: 11 },
    title: { font: { color: 'rgba(234,237,243,0.6)', size: 12 } },
  },
  title: {
    font: { color: '#eaedf3', size: 14, family: "'Inter', sans-serif" },
  },
  legend: {
    font: { color: 'rgba(234,237,243,0.6)', size: 11 },
    bgcolor: 'transparent',
    bordercolor: 'transparent',
  },
  hoverlabel: {
    bgcolor: 'rgba(15,17,26,0.92)',
    bordercolor: 'rgba(99,211,150,0.3)',
    font: { color: '#eaedf3', family: "'Inter', sans-serif", size: 12 },
  },
};

/* ── Enhance trace styling ── */
function enhanceTraces(data) {
  if (!Array.isArray(data)) return data;

  return data.map((trace) => {
    const enhanced = { ...trace };

    // Bar charts: gradient-like colors and rounded look
    if (trace.type === 'bar') {
      enhanced.marker = {
        ...trace.marker,
        line: { width: 0 },
        opacity: 0.9,
        color: trace.marker?.color || '#63d396',
      };
    }

    // Scatter: glow markers
    if (trace.type === 'scatter' || trace.type === 'scattergl') {
      enhanced.marker = {
        size: trace.marker?.size || 8,
        ...trace.marker,
        line: { width: 1, color: 'rgba(255,255,255,0.1)', ...(trace.marker?.line || {}) },
      };
    }

    // 3D scatter
    if (trace.type === 'scatter3d') {
      enhanced.marker = {
        size: trace.marker?.size || 4,
        opacity: 0.85,
        ...trace.marker,
        line: { width: 0.5, color: 'rgba(255,255,255,0.15)', ...(trace.marker?.line || {}) },
      };
    }

    // Pie/donut
    if (trace.type === 'pie') {
      enhanced.marker = {
        ...trace.marker,
        line: { color: 'rgba(6,8,16,0.8)', width: 2 },
      };
      enhanced.textfont = { color: '#eaedf3', size: 11 };
    }

    return enhanced;
  });
}

export default function PlotlyChart({ spec, image, title, height = 350 }) {
  const chartRef = useRef(null);

  useEffect(() => {
    if (spec && chartRef.current) {
      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
      };

      // Merge premium theme with spec layout
      const layout = {
        ...PREMIUM_THEME,
        ...spec.layout,
        height,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        margin: spec.layout?.margin || { l: 44, r: 20, t: 40, b: 34 },
        xaxis: { ...PREMIUM_THEME.xaxis, ...spec.layout?.xaxis },
        yaxis: { ...PREMIUM_THEME.yaxis, ...spec.layout?.yaxis },
        font: { ...PREMIUM_THEME.font, ...spec.layout?.font },
        hoverlabel: { ...PREMIUM_THEME.hoverlabel, ...spec.layout?.hoverlabel },
        title: spec.layout?.title
          ? { ...PREMIUM_THEME.title, ...(typeof spec.layout.title === 'string' ? { text: spec.layout.title } : spec.layout.title) }
          : undefined,
      };

      // Handle 3D scene
      if (spec.layout?.scene) {
        layout.scene = {
          ...spec.layout.scene,
          xaxis: {
            gridcolor: 'rgba(255,255,255,0.04)',
            backgroundcolor: 'rgba(6,8,16,0.3)',
            ...spec.layout.scene?.xaxis,
          },
          yaxis: {
            gridcolor: 'rgba(255,255,255,0.04)',
            backgroundcolor: 'rgba(6,8,16,0.3)',
            ...spec.layout.scene?.yaxis,
          },
          zaxis: {
            gridcolor: 'rgba(255,255,255,0.04)',
            backgroundcolor: 'rgba(6,8,16,0.3)',
            ...spec.layout.scene?.zaxis,
          },
          bgcolor: 'transparent',
        };
      }

      const enhancedData = enhanceTraces(spec.data);

      Plotly.newPlot(chartRef.current, enhancedData, layout, config);

      return () => {
        if (chartRef.current) {
          Plotly.purge(chartRef.current);
        }
      };
    }
  }, [spec, height]);

  if (spec) {
    return (
      <div
        ref={chartRef}
        style={{ width: '100%', height: `${height}px` }}
        className="plotly-container"
      />
    );
  }

  if (image) {
    return (
      <div className="static-chart-container">
        <img src={image} alt={title} style={{ maxWidth: '100%', height: 'auto', borderRadius: '8px' }} />
      </div>
    );
  }

  return <div className="chart-placeholder">Chart unavailable</div>;
}
