// The opening screen of the landing page, played like a film: the seven images (the statue, then Yasser's
// chain) take turns by themselves. On each change the old image flies out, a stream of golden light
// runs from it to the new one, the new image flies in, and the headline is written word by word.
// Dots and arrows jump to a scene (hovering them pauses the film); the keyboard arrows work too.
// For visitors who ask their system for less motion, nothing moves by itself.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./cinema.css";

const SCENE_MS = 5200;

export default function Cinema({ scenes, coverage }) {
  const [i, setI] = useState(0);
  const [prev, setPrev] = useState(null);
  const [paused, setPaused] = useState(false);
  const canvas = useRef(null);
  const stage = useRef(null);
  const still = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const go = (n) => {
    setPrev(i);
    setI((n + scenes.length) % scenes.length);
    stream();
  };

  useEffect(() => {                                // the film plays by itself
    if (paused || still) return;
    const t = setTimeout(() => go(i + 1), SCENE_MS);
    return () => clearTimeout(t);
  });

  useEffect(() => {                                // keyboard: left and right arrows
    const key = (e) => { if (e.key === "ArrowRight") go(i + 1); if (e.key === "ArrowLeft") go(i - 1); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  });

  // a stream of golden particles from the image that leaves to the one that arrives (the "coffee pour")
  const parts = useRef([]);
  function stream() {
    const c = canvas.current, box = stage.current?.getBoundingClientRect();
    if (!c || !box || still) return;
    const w = box.width, h = box.height;
    const from = { x: w * 0.78, y: h * 0.42 }, to = { x: w * 0.62, y: h * 0.58 };
    for (let k = 0; k < 160; k++) {
      parts.current.push({
        t: -Math.random() * 0.5, speed: 0.012 + Math.random() * 0.012,
        ax: from.x + (Math.random() - 0.5) * 160, ay: from.y - h * 0.45 + (Math.random() - 0.5) * 80,
        cx: w * (0.2 + Math.random() * 0.5), cy: h * (0.1 + Math.random() * 0.5),
        bx: to.x + (Math.random() - 0.5) * 220, by: to.y + (Math.random() - 0.5) * 160,
        size: 0.8 + Math.random() * 2.6, hue: 32 + Math.random() * 18,
      });
    }
  }

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const fit = () => {
      const box = stage.current.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio, 2);
      c.width = box.width * dpr; c.height = box.height * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    fit(); window.addEventListener("resize", fit);
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const box = stage.current.getBoundingClientRect();
      ctx.clearRect(0, 0, box.width, box.height);
      ctx.globalCompositeOperation = "lighter";
      parts.current = parts.current.filter((p) => p.t < 1);
      for (const p of parts.current) {
        p.t += p.speed;
        if (p.t < 0) continue;
        const t = p.t, u = 1 - t;                  // a curved path (quadratic Bezier) from a to b through c
        const x = u * u * p.ax + 2 * u * t * p.cx + t * t * p.bx, y = u * u * p.ay + 2 * u * t * p.cy + t * t * p.by;
        const alpha = Math.sin(Math.PI * t);
        const g = ctx.createRadialGradient(x, y, 0, x, y, p.size * 4);
        g.addColorStop(0, `hsla(${p.hue},100%,70%,${alpha})`); g.addColorStop(1, `hsla(${p.hue},100%,50%,0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, p.size * 4, 0, Math.PI * 2); ctx.fill();
      }
    };
    draw();
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", fit); };
  }, []);

  const s = scenes[i];
  const words = s.title.split(" ");
  return (
    <section className={`cin scene-${i}`} ref={stage}
             aria-roledescription="carousel" aria-label="What Verdicta does">
      <div className="cin-glow" style={{ left: `${55 + (i % 2) * 12}%`, top: `${42 + (i % 3) * 6}%` }} />
      <div key={`w${i}`} className="cin-word" aria-hidden="true">{s.word}</div>
      <canvas ref={canvas} className="cin-canvas" aria-hidden="true" />

      <div className="cin-stage" aria-hidden="true">
        {scenes.map((sc, k) => (
          <div key={sc.title} className={`cin-img ${k === i ? "in" : k === prev ? "out" : ""} ${k % 2 ? "alt" : ""}`}>
            <div className="lp-float3d" style={{ animationDelay: `${-k * 1.3}s` }}>
              <img src={sc.img} alt="" />
              <span className="lp-shine" style={{ "--m": `url(${sc.img}) center / contain no-repeat` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="cin-text" key={`t${i}`} aria-live="polite">
        <span className="cin-n">{i === 0 ? "" : `${i}.`}</span>
        {i === 0 && <span className="lp-kicker">U.S. Supreme Court research, verified</span>}
        <h1>
          {words.map((w, k) => (
            <span key={k} className={`cin-w ${(s.accent ?? [words.length - 1]).includes(k) ? "accent" : ""}`} style={{ animationDelay: `${0.25 + k * 0.08}s` }}>{w}</span>
          ))}
        </h1>
        <p className="cin-p">{s.text}</p>
        <p className="lp-cta">
          <Link to="/research" className="lp-button">Try a question</Link>
          <a href="#weigh" className="lp-button ghost">How it works ↓</a>
        </p>
        {i === 0 && <p className="lp-coverage">{coverage}</p>}
      </div>

      <div className="cin-controls" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
        <button className="cin-arrow" onClick={() => go(i - 1)} aria-label="Previous scene">‹</button>
        <div className="cin-dots">
          {scenes.map((sc, k) => (
            <button key={sc.title} onClick={() => go(k)} aria-label={`Scene ${k + 1}: ${sc.title}`} className={k === i ? "on" : ""}>
              {k === i && <i key={`p${i}`} className={paused || still ? "hold" : ""} style={{ animationDuration: `${SCENE_MS}ms` }} />}
            </button>
          ))}
        </div>
        <button className="cin-arrow" onClick={() => go(i + 1)} aria-label="Next scene">›</button>
      </div>
    </section>
  );
}
