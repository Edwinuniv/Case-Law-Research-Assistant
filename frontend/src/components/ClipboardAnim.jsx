// The court checklist beside the login and sign-up forms (images made by Yasser with ChatGPT, 2026-11-12):
// the pen leaves its place, goes to each of the six boxes in turn and "writes" its gold check (the check
// appears under the nib, left to right), then goes back; the six checks glow, fade, and it starts again.
// Six boxes like the verifier's six checks. Layers: the empty clipboard, the pen and the six checks, cut
// from the first image. Positions are in the pixels of the 1122 x 1402 image.
// For visitors who ask for less motion: all six checks shown, the pen at rest.
import { useEffect, useRef } from "react";
import board from "../assets/clipboard.webp";
import pen from "../assets/clip_pen.webp";
import c1 from "../assets/clip_check1.webp";
import c2 from "../assets/clip_check2.webp";
import c3 from "../assets/clip_check3.webp";
import c4 from "../assets/clip_check4.webp";
import c5 from "../assets/clip_check5.webp";
import c6 from "../assets/clip_check6.webp";

const W = 1122, H = 1402;
const PEN = { w: 368, h: 344, nib: [8, 341] };            // the pen image and where its nib is in it
const REST = [688, 1248];                                  // the nib's place at rest (as in the first image)
// each check: its image box [x, y, w, h], and the stroke the nib follows: start -> bottom of the V -> tip
const CHECKS = [
  { img: c1, box: [307, 463, 109, 100], path: [[319, 517], [348, 550], [404, 474]] },
  { img: c2, box: [316, 571, 109, 102], path: [[328, 627], [357, 660], [414, 583]] },
  { img: c3, box: [328, 681, 110, 105], path: [[340, 738], [369, 773], [426, 693]] },
  { img: c4, box: [342, 798, 110, 106], path: [[354, 855], [384, 891], [441, 809]] },
  { img: c5, box: [356, 911, 112, 109], path: [[368, 971], [398, 1007], [455, 923]] },
  { img: c6, box: [372, 1028, 114, 112], path: [[384, 1090], [414, 1127], [473, 1040]] },
];
const LOOP = 11, START = 0.6, STEP = 1.15, MOVE = 0.45, DRAW = 0.65;
const END = START + CHECKS.length * STEP;                  // 7.5 s: the last check is written
const clamp = (x) => Math.min(1, Math.max(0, x));
const ease = (x) => { x = clamp(x); return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; };
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const pct = (v, of) => `${(v / of) * 100}%`;

export default function ClipboardAnim() {
  const penRef = useRef(null);
  const checkRefs = useRef([]);
  const glowRefs = useRef([]);

  useEffect(() => {
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf;
    const t0 = performance.now();
    const frame = (now) => {
      raf = requestAnimationFrame(frame);
      const t = still ? 9 : ((now - t0) / 1000) % LOOP;
      // where the nib is, how lifted the pen is (0 on the paper, 1 in the air), and how far each check is drawn
      let nib = REST, lift = 0, tilt = 0;
      const drawn = CHECKS.map(() => 0);
      for (let k = 0; k < CHECKS.length; k++) {
        const s = START + k * STEP, c = CHECKS[k];
        if (t >= s + MOVE + DRAW) { drawn[k] = 1; continue; }
        if (t < s) break;
        const from = k === 0 ? REST : CHECKS[k - 1].path[2];
        if (t < s + MOVE) {                                // flying to the start of the check
          const u = ease((t - s) / MOVE);
          nib = mix(from, c.path[0], u); lift = Math.sin(Math.PI * u);
        } else {                                           // writing: down the short side, up the long side
          const u = (t - s - MOVE) / DRAW;
          nib = u < 0.35 ? mix(c.path[0], c.path[1], u / 0.35) : mix(c.path[1], c.path[2], (u - 0.35) / 0.65);
          tilt = 1;
          drawn[k] = clamp((nib[0] - c.box[0]) / c.box[2] + 0.06);
        }
        break;
      }
      if (t >= END) {                                      // back to its place
        const u = ease((t - END) / 0.8);
        nib = mix(CHECKS.at(-1).path[2], REST, u); lift = u < 1 ? Math.sin(Math.PI * u) : 0;
      }
      const fade = 1 - clamp((t - (LOOP - 0.8)) / 0.6);    // the six checks fade before the next round

      const p = penRef.current;
      if (p) {
        p.style.left = pct(nib[0] - PEN.nib[0], W);
        p.style.top = pct(nib[1] - PEN.nib[1], H);
        p.style.transform = `rotate(${-5 * tilt}deg) scale(${1 + 0.05 * lift})`;
        p.style.filter = `drop-shadow(${6 + 18 * lift}px ${8 + 22 * lift}px ${6 + 14 * lift}px rgba(0,0,0,${0.45 - 0.15 * lift}))`;
      }
      drawn.forEach((d, k) => {
        const el = checkRefs.current[k];
        if (el) { el.style.clipPath = `inset(0 ${(1 - d) * 100}% 0 0)`; el.style.opacity = fade; }
        const g = glowRefs.current[k];                     // a short glow when the check is finished
        if (g) {
          const done = START + k * STEP + MOVE + DRAW, after = t - done, end = t - END - 0.9;
          const flash = after > 0 && after < 0.7 ? 1 - after / 0.7 : 0, all = end > 0 && end < 1 ? Math.sin(Math.PI * end) : 0;
          g.style.opacity = Math.max(flash, all * 0.8) * fade;
        }
      });
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="clip" aria-hidden="true">
      <img src={board} alt="" className="clip-board" />
      {CHECKS.map((c, k) => (
        <span key={k}>
          <i ref={(el) => (glowRefs.current[k] = el)} className="clip-glow"
             style={{ left: pct(c.box[0] - 30, W), top: pct(c.box[1] - 30, H), width: pct(c.box[2] + 60, W), height: pct(c.box[3] + 60, H) }} />
          <img ref={(el) => (checkRefs.current[k] = el)} src={c.img} alt="" className="clip-check"
               style={{ left: pct(c.box[0], W), top: pct(c.box[1], H), width: pct(c.box[2], W), clipPath: "inset(0 100% 0 0)" }} />
        </span>
      ))}
      <img ref={penRef} src={pen} alt="" className="clip-pen"
           style={{ left: pct(REST[0] - PEN.nib[0], W), top: pct(REST[1] - PEN.nib[1], H), width: pct(PEN.w, W),
                    transformOrigin: `${(PEN.nib[0] / PEN.w) * 100}% ${(PEN.nib[1] / PEN.h) * 100}%` }} />
    </div>
  );
}
