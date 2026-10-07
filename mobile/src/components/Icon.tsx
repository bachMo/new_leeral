import Svg, { Circle, Path, Rect } from 'react-native-svg';

type Shape =
  { p: string } | { c: [number, number, number] } | { r: [number, number, number, number, number] };

type IconSpec = { shapes: Shape[]; fill?: boolean; sw?: number };

const ICONS = {
  speaker: {
    shapes: [
      { p: 'M4.5 9.5h3l4-3.5v12l-4-3.5h-3z' },
      { p: 'M15.5 9.5a3.5 3.5 0 0 1 0 5M18.5 7a7 7 0 0 1 0 10' },
    ],
  },
  speakerSmall: { shapes: [{ p: 'M4.5 9.5h3l4-3.5v12l-4-3.5h-3z' }, { p: 'M15.5 9.5a3.5 3.5 0 0 1 0 5' }] },
  sound: {
    shapes: [
      { p: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4z' },
      { p: 'M16 9a4.5 4.5 0 0 1 0 6M18.8 6.5a8 8 0 0 1 0 11' },
    ],
    sw: 2.2,
  },
  soundSmall: { shapes: [{ p: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4z' }, { p: 'M16 9a4.5 4.5 0 0 1 0 6' }] },
  soundBare: { shapes: [{ p: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4z' }] },
  back: { shapes: [{ p: 'M15 5l-7 7 7 7' }], sw: 2.2 },
  close: { shapes: [{ p: 'M6 6l12 12M18 6L6 18' }], sw: 2.2 },
  globe: {
    shapes: [
      { c: [12, 12, 9] },
      { p: 'M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z' },
    ],
  },
  user: { shapes: [{ c: [12, 8.5, 3.8] }, { p: 'M4.5 20c1.3-3.6 4.2-5.4 7.5-5.4s6.2 1.8 7.5 5.4' }] },
  camera: {
    shapes: [
      {
        p: 'M4 8.5A1.5 1.5 0 0 1 5.5 7h2.2l1.6-2.2h5.4L16.3 7h2.2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z',
      },
      { c: [12, 12.8, 3.4] },
    ],
  },
  file: { shapes: [{ p: 'M7 3h7l5 5v13H7z' }, { p: 'M14 3v5h5' }] },
  fileLines: { shapes: [{ p: 'M7 3h7l5 5v13H7z' }, { p: 'M10 13h6M10 17h4' }] },
  image: { shapes: [{ r: [3.5, 4.5, 17, 15, 2.5] }, { c: [9, 10, 1.8] }, { p: 'M20.5 16l-5-5-8.5 8.5' }] },
  pen: { shapes: [{ p: 'M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z' }, { p: 'M13.5 6.5l4 4' }] },
  penBare: { shapes: [{ p: 'M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z' }] },
  book: {
    shapes: [
      { p: 'M3 6.5C5.5 5 8.5 5 12 7c3.5-2 6.5-2 9-.5V19c-2.5-1.5-5.5-1.5-9 .5-3.5-2-6.5-2-9-.5z' },
      { p: 'M12 7v12.5' },
    ],
  },
  bookBare: {
    shapes: [{ p: 'M3 6.5C5.5 5 8.5 5 12 7c3.5-2 6.5-2 9-.5V19c-2.5-1.5-5.5-1.5-9 .5-3.5-2-6.5-2-9-.5z' }],
  },
  bookmark: { shapes: [{ p: 'M5 4h14v17l-7-4.5L5 21z' }] },
  home: { shapes: [{ p: 'M4 10.5L12 4l8 6.5V20h-5v-6H9v6H4z' }] },
  play: { shapes: [{ p: 'M8 5.5v13l11-6.5z' }], fill: true },
  pause: { shapes: [{ r: [6.5, 5, 4, 14, 1.2] }, { r: [13.5, 5, 4, 14, 1.2] }], fill: true },
  send: { shapes: [{ p: 'M3.5 11.2L20 4l-7.2 16.5-2.1-7.2z' }], fill: true },
  check: { shapes: [{ p: 'M5 12.5l4.5 4.5L19 7.5' }], sw: 2.8 },
  arrow: { shapes: [{ p: 'M5 12h14M13 6l6 6-6 6' }], sw: 2.4 },
  lock: { shapes: [{ r: [5, 10.5, 14, 10, 2] }, { p: 'M8 10.5V7.5a4 4 0 0 1 8 0v3' }] },
  clock: { shapes: [{ c: [12, 12, 9] }, { p: 'M12 7v5l3 2' }] },
  mic: { shapes: [{ r: [9, 3, 6, 11, 3] }, { p: 'M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21' }], sw: 2.2 },
  keyboard: { shapes: [{ r: [3, 6, 18, 12, 2] }, { p: 'M7 10h.01M11 10h.01M15 10h.01M8 14h8' }] },
  sun: {
    shapes: [
      { c: [12, 12, 4] },
      {
        p: 'M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4',
      },
    ],
  },
  flat: { shapes: [{ p: 'M3 16h18M6 16l2-8h8l2 8' }] },
  phone: { shapes: [{ r: [7, 3, 10, 18, 2] }, { p: 'M11 18h2' }] },
  retry: { shapes: [{ p: 'M4 12a8 8 0 1 0 2.4-5.7' }, { p: 'M4 4v4.5h4.5' }], sw: 2.2 },
  alert: { shapes: [{ p: 'M12 7v6M12 17h.01' }], sw: 2.6 },
  calendar: { shapes: [{ r: [4, 5, 16, 15, 2] }, { p: 'M4 10h16M9 3v4M15 3v4' }] },
  info: { shapes: [{ c: [12, 12, 9] }, { p: 'M12 8v4M12 16h.01' }] },
  trash: { shapes: [{ p: 'M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13' }] },
  logout: { shapes: [{ p: 'M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10' }] },
  addUser: {
    shapes: [{ c: [9, 8, 3.2] }, { p: 'M3.5 19c1-3 3-4.5 5.5-4.5s4.5 1.5 5.5 4.5M16 7.5h5M18.5 5v5' }],
  },
  download: { shapes: [{ p: 'M12 4v11M7 10.5l5 5 5-5M5 20h14' }] },
  share: { shapes: [{ p: 'M4 12l16-8-6 16-2.5-6.5z' }] },
  speed: { shapes: [{ p: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4zM16 9a4.5 4.5 0 0 1 0 6' }] },
  help: {
    shapes: [
      {
        p: 'M12 21a9 9 0 1 0-8-4.9L3 21l4.9-1A9 9 0 0 0 12 21zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5M12 16.5h.01',
      },
    ],
  },
  globeRow: {
    shapes: [
      {
        p: 'M3 12h18M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z',
      },
    ],
  },
  docRow: { shapes: [{ p: 'M7 3h7l5 5v13H7zM14 3v5h5' }] },
} satisfies Record<string, IconSpec>;

export type IconName = keyof typeof ICONS;

type Props = {
  name?: IconName;
  path?: string;
  size?: number;
  color?: string;
  strokeWidth?: number;
};

export function Icon({ name, path, size = 20, color = '#12233B', strokeWidth }: Props) {
  const spec: IconSpec = name ? ICONS[name] : { shapes: path ? [{ p: path }] : [] };
  const fill = spec.fill ? color : 'none';
  const stroke = spec.fill ? 'none' : color;
  const width = strokeWidth ?? spec.sw ?? 2;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" pointerEvents="none">
      {spec.shapes.map((shape, index) => {
        const common = {
          fill,
          stroke,
          strokeWidth: width,
          strokeLinecap: 'round' as const,
          strokeLinejoin: 'round' as const,
        };
        if ('p' in shape) return <Path key={index} {...common} d={shape.p} />;
        if ('c' in shape)
          return <Circle key={index} {...common} cx={shape.c[0]} cy={shape.c[1]} r={shape.c[2]} />;
        return (
          <Rect
            key={index}
            {...common}
            x={shape.r[0]}
            y={shape.r[1]}
            width={shape.r[2]}
            height={shape.r[3]}
            rx={shape.r[4]}
          />
        );
      })}
    </Svg>
  );
}
