import { useRef, useState, useCallback, useEffect } from "react";

export default function KpiCard({ icon, label, value, subtitle, color }) {
  const cardRef = useRef(null);
  const glowRef = useRef(null);
  const [displayValue, setDisplayValue] = useState(value);

  // Animated counter for numeric values
  useEffect(() => {
    const numericStr = String(value ?? "").replace(/[^0-9.]/g, "");
    const num = parseFloat(numericStr);
    if (!isNaN(num) && num > 0 && num <= 999999) {
      const suffix = String(value ?? "").replace(/[0-9.,]/g, "");
      const hasComma = String(value ?? "").includes(",");
      let start = 0;
      const duration = 800;
      const startTime = performance.now();

      const animate = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(eased * num);
        setDisplayValue(
          (hasComma ? current.toLocaleString() : current) + suffix
        );
        if (progress < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    } else {
      setDisplayValue(value);
    }
  }, [value]);

  // 3D tilt on mouse move
  const handleMouseMove = useCallback((e) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const rotateX = ((y - centerY) / centerY) * -4;
    const rotateY = ((x - centerX) / centerX) * 4;

    cardRef.current.style.transform = `perspective(600px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(4px)`;

    if (glowRef.current) {
      glowRef.current.style.left = `${x}px`;
      glowRef.current.style.top = `${y}px`;
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (cardRef.current) {
      cardRef.current.style.transform = "perspective(600px) rotateX(0) rotateY(0) translateZ(0)";
    }
  }, []);

  return (
    <div
      ref={cardRef}
      className="kpi-card"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div ref={glowRef} className="kpi-glow" />
      <div
        className="kpi-icon"
        style={{ background: `${color || "rgba(99,211,150,0.08)"}` }}
      >
        {icon}
      </div>
      <div className="kpi-info">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{displayValue ?? "—"}</div>
        {subtitle && <div className="kpi-subtitle">{subtitle}</div>}
      </div>
    </div>
  );
}
