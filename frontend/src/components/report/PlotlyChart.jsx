import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

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

      const layout = {
        ...spec.layout,
        height,
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        margin: spec.layout?.margin || { l: 40, r: 20, t: 40, b: 30 },
      };

      Plotly.newPlot(chartRef.current, spec.data, layout, config);

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
        <img src={image} alt={title} style={{ maxWidth: '100%', height: 'auto' }} />
      </div>
    );
  }

  return <div className="chart-placeholder">Chart unavailable</div>;
}
