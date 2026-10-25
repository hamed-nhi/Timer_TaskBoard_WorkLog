import { useId } from "react";

export function BrandMark() {
  const id = useId();
  const bg = `mark-bg-${id}`, arc = `mark-arc-${id}`;
  return (
    <svg className="brand-mark" viewBox="0 0 100 100" role="img" aria-label="TIME LOG">
      <defs>
        <linearGradient id={bg} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4f46e5" /><stop offset="1" stopColor="#7c3aed" /></linearGradient>
        <linearGradient id={arc} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fde047" /><stop offset="1" stopColor="#f97316" /></linearGradient>
      </defs>
      <rect x="4" y="4" width="92" height="92" rx="24" fill={`url(#${bg})`} />
      <circle cx="50" cy="52" r="29" fill="none" stroke="#fff" strokeOpacity=".22" strokeWidth="8.5" />
      <circle cx="50" cy="52" r="29" fill="none" stroke={`url(#${arc})`} strokeWidth="8.5" strokeLinecap="round" strokeDasharray="136.6 182.2" transform="rotate(-90 50 52)" />
      <path d="M50 52V36.5M50 52l9.1 5.25" stroke="#fff" strokeWidth="5" strokeLinecap="round" fill="none" />
      <circle cx="50" cy="52" r="3.6" fill="#fff" />
    </svg>
  );
}
