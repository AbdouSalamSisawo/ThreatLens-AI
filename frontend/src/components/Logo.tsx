/* ThreatLens AI wordmark: shield + lens mark, consistent across the app. */

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="ThreatLens AI logo"
    >
      <path
        d="M32 8 L50 15 V30 C50 43 42.5 52 32 56 C21.5 52 14 43 14 30 V15 Z"
        fill="none"
        stroke="#38D9C3"
        strokeWidth="3"
      />
      <circle
        cx="32"
        cy="30"
        r="9"
        fill="none"
        stroke="#66B9FF"
        strokeWidth="2.5"
      />
      <line
        x1="38.5"
        y1="36.5"
        x2="46"
        y2="44"
        stroke="#66B9FF"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx="32" cy="30" r="3" fill="#38D9C3" />
    </svg>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={compact ? 24 : 28} />
      <span className="leading-none">
        <span className="block font-semibold tracking-tight text-text">
          ThreatLens<span className="text-accent"> AI</span>
        </span>
        {!compact && (
          <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
            Explainable URL Detection
          </span>
        )}
      </span>
    </span>
  );
}
