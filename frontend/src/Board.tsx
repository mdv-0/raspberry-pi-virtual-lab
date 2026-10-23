import type { Status } from "./types";
type Props = { status: Status; selected: string; select: (id: string) => void };
export function Board({ status, selected, select }: Props) {
  const inserted = status.media.some((m) => m.state !== "AVAILABLE");
  const port = (
    id: string,
    label: string,
    x: number,
    y: number,
    width: number,
    height: number,
  ) => (
    <g
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={selected === id}
      className={`board-connector ${selected === id ? "selected" : ""}`}
      onClick={() => select(id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select(id);
        }
      }}
    >
      <rect x={x} y={y} width={width} height={height} rx="4" />
      <text x={x + width / 2} y={y + height / 2 + 4} textAnchor="middle">
        {label}
      </text>
    </g>
  );
  return (
    <svg
      viewBox="0 0 650 330"
      className="board-svg"
      aria-label={`Interactive ${status.profile.name}`}
    >
      <defs>
        <linearGradient id="pcb" x2="0" y2="1">
          <stop stopColor="var(--board-top)" />
          <stop offset="1" stopColor="var(--board-bottom)" />
        </linearGradient>
        <filter id="board-shadow" x="-30%" y="-30%" width="160%" height="180%">
          <feDropShadow
            dx="0"
            dy="14"
            stdDeviation="16"
            floodColor="#000"
            floodOpacity=".14"
          />
        </filter>
      </defs>
      <rect
        x="83"
        y="35"
        width="484"
        height="253"
        rx="17"
        fill="url(#pcb)"
        stroke="var(--board-line)"
        filter="url(#board-shadow)"
      />
      {[
        [103, 55],
        [547, 55],
        [103, 268],
        [547, 268],
      ].map(([x, y]) => (
        <g key={x + ":" + y}>
          <circle cx={x} cy={y} r="8" fill="#bac5d6" />
          <circle cx={x} cy={y} r="4" fill="#111824" />
        </g>
      ))}
      <g stroke="#9acbb0" fill="none" opacity=".35">
        <path d="M 265 140 H 218 V 112 H 135 M 265 155 H 192 V 178 H 145 M 376 140 H 417 V 102 H 512 M 376 205 H 435 V 222 H 511 M 284 220 V 258 H 248 M 352 220 V 257 H 448" />
      </g>
      <text
        x="128"
        y="92"
        fill="#e3e9f2"
        fontSize="17"
        fontWeight="500"
        letterSpacing="2"
      >
        ARM64
      </text>
      <text x="129" y="108" fill="#bdc9db" fontSize="8" letterSpacing="1.5">
        VIRTUAL LAB
      </text>
      <g
        role="button"
        tabIndex={0}
        aria-label="GPIO information"
        aria-pressed={selected === "gpio0"}
        onClick={() => select("gpio0")}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            select("gpio0");
          }
        }}
        className="gpio-header"
      >
        <rect
          x="247"
          y="53"
          width="232"
          height="29"
          rx="3"
          fill="#232a2c"
          stroke="#7486a0"
        />
        {Array.from({ length: 20 }, (_, i) => (
          <g key={i} fill="#c9af76">
            <rect x={253 + i * 11} y="59" width="4" height="5" />
            <rect x={253 + i * 11} y="70" width="4" height="5" />
          </g>
        ))}
      </g>
      <rect
        x="265"
        y="128"
        width="110"
        height="92"
        rx="5"
        fill="#181e21"
        stroke="#7e90ab"
      />
      <rect x="274" y="137" width="92" height="74" rx="2" fill="#2c3439" />
      {Array.from({ length: 10 }, (_, i) => (
        <g key={i} fill="#aab9d1">
          <rect x={274 + i * 9} y="123" width="3" height="5" />
          <rect x={274 + i * 9} y="220" width="3" height="5" />
        </g>
      ))}
      <text
        x="320"
        y="167"
        fill="#f1f5fc"
        textAnchor="middle"
        fontSize="11"
        fontWeight="500"
      >
        Cortex-A53
      </text>
      <rect
        x="411"
        y="126"
        width="65"
        height="35"
        rx="3"
        fill="#242c30"
        stroke="#6e83a2"
      />
      <text x="443" y="147" fill="#c1cde0" textAnchor="middle" fontSize="8">
        RAM
      </text>
      {[195, 212, 229, 402, 419, 436, 453].map((x, i) => (
        <rect
          key={x}
          x={x}
          y={i < 3 ? 143 : 186}
          width="7"
          height="11"
          rx="1"
          fill="#a3b3cb"
          opacity=".6"
        />
      ))}
      {port("net0", "ETHERNET", 73, 158, 102, 61)}
      <g stroke="#d0daea" opacity=".45">
        {Array.from({ length: 8 }, (_, i) => (
          <path key={i} d={`M ${87 + i * 10} 166 v 10`} />
        ))}
      </g>
      {port("uart0", "UART", 483, 199, 94, 37)}
      {port("boot0", "BOOT MEDIA", 201, 264, 111, 38)}
      {inserted && (
        <g>
          <rect
            x="221"
            y="289"
            width="71"
            height="28"
            rx="3"
            fill="#233045"
            stroke="#7f96b8"
          />
          <text x="256" y="307" fill="#d0ddf3" textAnchor="middle" fontSize="8">
            {status.profile.id === "raspi3b" ? "SD/MMC" : "disk"}
          </text>
        </g>
      )}
      {port("display0", "DISPLAY", 398, 264, 103, 38)}
      <circle
        cx="132"
        cy="250"
        r="3"
        fill={status.power === "RUNNING" ? "#6ee7ad" : "#6f819b"}
      />
      <text x="143" y="253" fill="#c2cfe3" fontSize="8">
        PWR
      </text>
      <circle
        cx="490"
        cy="247"
        r="2.5"
        fill={status.uart.mode !== "disconnected" ? "#6ee7ad" : "#6f819b"}
      />
      <circle
        cx="162"
        cy="226"
        r="2.5"
        fill={status.network.link ? "#6ee7ad" : "#6f819b"}
      />
    </svg>
  );
}
