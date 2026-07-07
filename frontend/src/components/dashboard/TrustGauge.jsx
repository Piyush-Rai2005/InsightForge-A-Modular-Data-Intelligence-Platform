import { useEffect, useState } from "react";

export default function TrustGauge({ score = 0 }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;

  const color =
    animatedScore >= 80 ? "#63d396" : animatedScore >= 50 ? "#f59e0b" : "#ff5f6d";
  const glowColor =
    animatedScore >= 80
      ? "rgba(99,211,150,0.25)"
      : animatedScore >= 50
      ? "rgba(245,158,11,0.2)"
      : "rgba(255,95,109,0.2)";
  const label =
    animatedScore >= 80
      ? "Excellent"
      : animatedScore >= 50
      ? "Moderate"
      : "Poor";

  // Gradient ID unique per instance
  const gradId = `gauge-grad-${score}`;

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(Math.min(score, 100)), 100);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="trust-gauge">
      {/* Ambient glow behind gauge */}
      <div
        className="trust-gauge-glow"
        style={{ background: `radial-gradient(circle, ${glowColor}, transparent 70%)` }}
      />

      <svg width="150" height="150" viewBox="0 0 150 150">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} />
            <stop
              offset="100%"
              stopColor={
                animatedScore >= 80
                  ? "#4ac2dc"
                  : animatedScore >= 50
                  ? "#fbbf24"
                  : "#ff8a80"
              }
            />
          </linearGradient>
          {/* Glow filter */}
          <filter id="gauge-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background circle */}
        <circle
          cx="75" cy="75" r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.04)"
          strokeWidth="10"
        />

        {/* Animated progress circle with gradient + glow */}
        <circle
          cx="75" cy="75" r={radius}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 75 75)"
          filter="url(#gauge-glow)"
          style={{
            transition: "stroke-dashoffset 1.4s cubic-bezier(0.22, 1, 0.36, 1), stroke 0.5s ease",
          }}
        />

        {/* Score text */}
        <text
          x="75" y="69"
          textAnchor="middle"
          fill={color}
          fontSize="30"
          fontWeight="700"
          fontFamily="'Inter', sans-serif"
        >
          {animatedScore}
        </text>
        <text
          x="75" y="90"
          textAnchor="middle"
          fill="rgba(255,255,255,0.35)"
          fontSize="11"
          fontFamily="'Inter', sans-serif"
        >
          / 100
        </text>
      </svg>
      <div className="trust-gauge-label" style={{ color }}>{label}</div>
    </div>
  );
}
