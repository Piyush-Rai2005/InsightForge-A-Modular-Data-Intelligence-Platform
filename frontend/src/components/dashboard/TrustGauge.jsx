import { useEffect, useState } from "react";

export default function TrustGauge({ score = 0 }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;

  const color =
    animatedScore >= 80 ? "#63d396" : animatedScore >= 50 ? "#f59e0b" : "#ff5f6d";
  const label =
    animatedScore >= 80
      ? "Excellent"
      : animatedScore >= 50
      ? "Moderate"
      : "Poor";

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(Math.min(score, 100)), 100);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="trust-gauge">
      <svg width="140" height="140" viewBox="0 0 140 140">
        {/* Background circle */}
        <circle
          cx="70" cy="70" r={radius}
          fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10"
        />
        {/* Animated progress circle */}
        <circle
          cx="70" cy="70" r={radius}
          fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
          style={{ transition: "stroke-dashoffset 1.2s ease-out, stroke 0.5s ease" }}
        />
        {/* Score text */}
        <text x="70" y="64" textAnchor="middle" fill={color} fontSize="28" fontWeight="700" fontFamily="'Syne', sans-serif">
          {animatedScore}
        </text>
        <text x="70" y="84" textAnchor="middle" fill="rgba(255,255,255,0.5)" fontSize="11">
          / 100
        </text>
      </svg>
      <div className="trust-gauge-label" style={{ color }}>{label}</div>
    </div>
  );
}
