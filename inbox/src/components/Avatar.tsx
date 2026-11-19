import { initials, windowFraction } from "../lib/format";

interface AvatarProps {
  name: string | null;
  phone: string;
  windowExpiresAt: string | null;
  now: number;
  large?: boolean;
}

export function Avatar({ name, phone, windowExpiresAt, now, large = false }: AvatarProps) {
  const size = large ? 76 : 46;
  const stroke = large ? 4 : 3;
  const radius = size / 2 - stroke / 2 - 0.5;
  const circumference = 2 * Math.PI * radius;
  const fraction = windowFraction(windowExpiresAt, now);
  const low = fraction > 0 && fraction < 2 / 24;
  return (
    <div className={`avatar${large ? " is-large" : ""}`} aria-hidden="true">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#DFE4EC"
          strokeWidth={stroke}
        />
        {fraction > 0 && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={low ? "#B42318" : "#F5A524"}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${circumference * fraction} ${circumference}`}
          />
        )}
      </svg>
      <div className="avatar-face">{initials(name, phone)}</div>
    </div>
  );
}
