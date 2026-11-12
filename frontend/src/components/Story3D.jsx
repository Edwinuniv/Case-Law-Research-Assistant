// The top of the landing page: a short 3D film that plays by itself (Three.js, real moving objects).
// Like the coffee site, each scene shows ONE object alone, and THE PAGE travels from one to the next:
//   1. the statue: the page comes out from behind her and flies away;
//   2. the scale: the page lands on a pan, which sinks under it, then flies on;
//   3. the book: the page lands on it and the book's pages fan open;
//   4. the magnifying glass: a swirl of golden light gathers into it, and it slides across the page;
//   5. the check: the light gathers again and a gold check rises out of the page.
// Then it loops. The headline changes with each scene. The objects are built from simple shapes here;
// only the statue is an image (Yasser's). It stops drawing when off screen; for visitors who ask for
// less motion it shows one still frame.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import "./story3d.css";

const LOOP = 23;                                          // seconds for the whole film
const PARTS = [0, 4.5, 8.8, 13.5, 18.3];                  // start time of each scene
const clamp = (x) => Math.min(1, Math.max(0, x));
const ease = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const win = (t, a, b) => ease((t - a) / (b - a));         // 0 before a, 1 after b, smooth in between
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const bezier = (a, c, b, u) => a.clone().multiplyScalar((1 - u) * (1 - u)).add(c.clone().multiplyScalar(2 * u * (1 - u))).add(b.clone().multiplyScalar(u * u));

function paperTexture() {                                 // THE PAGE: cream paper, grey lines, a gold edge
  const c = document.createElement("canvas"); c.width = 512; c.height = 700;
  const g = c.getContext("2d");
  g.fillStyle = "#efe3c6"; g.fillRect(0, 0, 512, 700);
  g.strokeStyle = "#c9a24d"; g.lineWidth = 10; g.strokeRect(5, 5, 502, 690);
  g.fillStyle = "rgba(90,80,70,.45)";
  for (let y = 80; y < 640; y += 30) g.fillRect(56, y, (y % 150 === 80 ? 260 : 400) - Math.random() * 40, 9);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function glowTexture() {                                  // a soft round light, for the flash
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d"), r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, "rgba(255,240,200,1)"); r.addColorStop(0.3, "rgba(255,190,80,.6)"); r.addColorStop(1, "rgba(255,150,40,0)");
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export default function Story3D({ scenes, statue, coverage }) {
  const mount = useRef(null);
  const statueImg = useRef(null);
  const [part, setPart] = useState(0);

  useEffect(() => {
    const host = mount.current;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, 2.6, 12); camera.lookAt(0, 0.6, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const key = new THREE.DirectionalLight(0xffb347, 3.4); key.position.set(4, 7, 6); scene.add(key);
    const rim = new THREE.DirectionalLight(0xff7a1a, 2.6); rim.position.set(-6, 3, -4); scene.add(rim);

    const gold = new THREE.MeshStandardMaterial({ color: 0xd9a441, metalness: 1, roughness: 0.25 });
    const bronze = new THREE.MeshStandardMaterial({ color: 0xb06a32, metalness: 1, roughness: 0.32 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1d1d22, metalness: 0.6, roughness: 0.45 });
    const leather = new THREE.MeshStandardMaterial({ color: 0x4a2814, metalness: 0.1, roughness: 0.6 });
    const pages = new THREE.MeshStandardMaterial({ color: 0xeadcbc, roughness: 0.8 });
    const wood = new THREE.MeshStandardMaterial({ color: 0x5a2f17, metalness: 0.15, roughness: 0.4 });
    const additive = (color, extra = {}) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, ...extra });
    const mesh = (geo, mat, parent, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; };
    const group = (parent = scene) => { const g = new THREE.Group(); parent.add(g); return g; };

    // ---------- the scale ----------
    const scale = group();
    mesh(new THREE.CylinderGeometry(1.2, 1.4, 0.26, 64), dark, scale, 0, 0.13, 0);
    mesh(new THREE.CylinderGeometry(0.9, 1.05, 0.16, 64), bronze, scale, 0, 0.34, 0);
    mesh(new THREE.CylinderGeometry(0.11, 0.15, 3.1, 32), bronze, scale, 0, 1.95, 0);
    mesh(new THREE.SphereGeometry(0.2, 32, 16), gold, scale, 0, 3.7, 0);
    const beam = group(scale); beam.position.set(0, 3.45, 0);
    mesh(new THREE.CylinderGeometry(0.05, 0.05, 3.6, 24), bronze, beam).rotation.z = Math.PI / 2;
    const pans = [-1, 1].map((side) => {
      const h = group(beam); h.position.x = side * 1.8;
      for (let k = 0; k < 3; k++) {
        const a = (k / 3) * Math.PI * 2, end = V(Math.cos(a) * 0.68, -1.6, Math.sin(a) * 0.68);
        const c = mesh(new THREE.CylinderGeometry(0.012, 0.012, end.length(), 6), gold, h, end.x / 2, end.y / 2, end.z / 2);
        c.quaternion.setFromUnitVectors(V(0, 1, 0), end.clone().normalize());
      }
      const bowl = new THREE.LatheGeometry([new THREE.Vector2(0, -0.18), new THREE.Vector2(0.45, -0.15),
        new THREE.Vector2(0.66, -0.05), new THREE.Vector2(0.7, 0)], 64);
      mesh(bowl, new THREE.MeshStandardMaterial({ color: 0xc98a45, metalness: 1, roughness: 0.22, side: THREE.DoubleSide }), h, 0, -1.6, 0);
      const anchor = new THREE.Object3D(); anchor.position.set(0, -1.6, 0); h.add(anchor);
      return { h, anchor };
    });

    // ---------- THE PAGE: a bendable sheet ----------
    const paperGeo = new THREE.PlaneGeometry(1.25, 1.7, 24, 24);
    const flat = paperGeo.attributes.position.array.slice();
    const paperMat = new THREE.MeshStandardMaterial({ map: paperTexture(), roughness: 0.85, side: THREE.DoubleSide,
      emissive: 0xffa53a, emissiveIntensity: 0 });
    const paper = mesh(paperGeo, paperMat, scene);
    const bend = (amount, time) => {                      // the sheet waves like paper in the air
      const p = paperGeo.attributes.position.array;
      for (let v = 0; v < p.length; v += 3) {
        const x = flat[v], y = flat[v + 1];
        p[v + 2] = amount * (Math.sin(x * 2.6 + time * 5) * 0.22 + Math.sin(y * 1.8 - time * 4) * 0.16 + x * x * 0.2);
      }
      paperGeo.attributes.position.needsUpdate = true; paperGeo.computeVertexNormals();
    };
    const glow = mesh(new THREE.PlaneGeometry(1.0, 0.09), additive(0xffb347, { side: THREE.FrontSide }), paper, 0, 0.1, 0.02);

    // ---------- the open book ----------
    const book = group();
    for (const side of [-1, 1]) {
      const half = group(book); half.rotation.z = side * -0.12;
      mesh(new THREE.BoxGeometry(1.9, 0.08, 2.6), leather, half, side * 0.98, 0, 0);
      mesh(new THREE.BoxGeometry(1.8, 0.32, 2.45), pages, half, side * 0.95, 0.2, 0);
    }
    mesh(new THREE.BoxGeometry(4.1, 0.55, 2.8), leather, book, 0, -0.42, 0);    // a second, closed book under it
    mesh(new THREE.BoxGeometry(4.0, 0.03, 2.7), gold, book, 0, -0.14, 0);
    const fan = [];
    for (let k = 0; k < 7; k++) {                         // loose pages hinged at the spine, fanning open
      const hinge = group(book); hinge.position.y = 0.38;
      const sheet = mesh(new THREE.PlaneGeometry(1.75, 2.35), new THREE.MeshStandardMaterial({ color: 0xf1e6cc, roughness: 0.8, side: THREE.DoubleSide }), hinge, 0.88, 0, 0);
      sheet.rotation.x = -Math.PI / 2;
      fan.push(hinge);
    }

    // ---------- the magnifying glass (facing us) ----------
    const glass = group();
    mesh(new THREE.TorusGeometry(0.62, 0.07, 24, 64), gold, glass);
    mesh(new THREE.CircleGeometry(0.6, 48), new THREE.MeshPhysicalMaterial({ color: 0xfff3d6, metalness: 0, roughness: 0.05,
      transmission: 0.9, transparent: true, opacity: 0.3, thickness: 0.2 }), glass);
    const handle = mesh(new THREE.CylinderGeometry(0.07, 0.09, 1.3, 24), wood, glass, 0.95, -0.95, 0);
    handle.rotation.z = Math.PI / 4;
    mesh(new THREE.TorusGeometry(0.085, 0.025, 12, 24), gold, glass, 0.52, -0.52, 0).rotation.y = Math.PI / 2;

    // ---------- the gold check ----------
    const chk = new THREE.Shape();
    chk.moveTo(-0.55, 0.05); chk.lineTo(-0.35, 0.25); chk.lineTo(-0.12, 0.0); chk.lineTo(0.5, 0.75);
    chk.lineTo(0.68, 0.55); chk.lineTo(-0.12, -0.38); chk.closePath();
    const checkGeo = new THREE.ExtrudeGeometry(chk, { depth: 0.16, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.04, bevelSegments: 4 });
    checkGeo.center();
    const check = mesh(checkGeo, new THREE.MeshStandardMaterial({ color: 0xf2b545, metalness: 1, roughness: 0.18,
      emissive: 0x6b3a00, emissiveIntensity: 0.6 }), scene);

    // ---------- the "something beautiful": a swirl of golden light that gathers into an object ----------
    const N = 520, swirlPos = new Float32Array(N * 3), seeds = [];
    for (let k = 0; k < N; k++) seeds.push({ a: Math.random() * Math.PI * 2, r: 1.0 + Math.random() * 1.7,
      h: (Math.random() - 0.5) * 2.6, s: 0.6 + Math.random() * 0.8, v: V((Math.random() - 0.5) * 2, Math.random() * 2 + 0.4, (Math.random() - 0.5) * 2) });
    const swirlGeo = new THREE.BufferGeometry(); swirlGeo.setAttribute("position", new THREE.BufferAttribute(swirlPos, 3));
    const swirlMat = new THREE.PointsMaterial({ color: 0xffc34d, size: 0.06, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    scene.add(new THREE.Points(swirlGeo, swirlMat));
    const gather = (target, k, time) => {                 // k: 0 = spread around, 1 = all at the target
      for (let i = 0; i < N; i++) {
        const s = seeds[i], u = 1 - ease(clamp(k * s.s + (1 - s.s) * k * k)), a = s.a + k * 6 + time * 0.4;
        swirlPos[i * 3] = target.x + Math.cos(a) * s.r * u;
        swirlPos[i * 3 + 1] = target.y + s.h * u;
        swirlPos[i * 3 + 2] = target.z + Math.sin(a) * s.r * u * 0.6;
      }
      swirlGeo.attributes.position.needsUpdate = true;
    };
    const burst = (origin, age) => {                      // the same lights thrown out again, falling
      for (let i = 0; i < N; i++) {
        const v = seeds[i].v;
        swirlPos[i * 3] = origin.x + v.x * age; swirlPos[i * 3 + 1] = origin.y + v.y * age - 1.2 * age * age; swirlPos[i * 3 + 2] = origin.z + v.z * age;
      }
      swirlGeo.attributes.position.needsUpdate = true;
    };
    const flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false }));
    scene.add(flash);
    const ring = mesh(new THREE.RingGeometry(0.9, 0.97, 96), additive(0xffb347), scene);

    let width = 1, height = 1;
    const resize = () => {
      width = host.clientWidth; height = host.clientHeight;
      renderer.setSize(width, height); camera.aspect = width / height;
      // on a wide screen the text is on the left, so the objects are drawn a bit to the right
      if (width > 900) camera.setViewOffset(width, height, -width * 0.17, 0, width, height); else camera.clearViewOffset();
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize); ro.observe(host); resize();
    let visible = true;
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.05 });
    io.observe(host);

    // an object comes in from far behind, and later leaves backwards to the left, fading
    const stage = (obj, t, inA, outA, base) => {
      const i = win(t, inA, inA + 0.9), o = win(t, outA, outA + 0.9), a = i * (1 - o);
      obj.visible = a > 0.001;
      obj.scale.setScalar(Math.max(0.001, 0.4 + 0.6 * i) * (1 - 0.6 * o));
      obj.position.set(base.x - 4 * o, base.y, base.z - 9 * (1 - i) - 4 * o);
      return a;
    };

    const clock = new THREE.Clock();
    const pt = new THREE.Vector3();
    let raf, lastPart = -1;

    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;
      const now = window.__st3dTime ?? clock.getElapsedTime();   // __st3dTime: only set by our recording script, to film frame by frame
      const t = still ? 20.5 : now % LOOP;

      // 1. the statue (an image above the canvas): she appears, the page comes out from behind her, she fades
      const st = statueImg.current;
      if (st) {
        const o = win(t, 0, 0.8) * (1 - win(t, 3.6, 4.6));
        st.style.opacity = o;
        st.style.transform = `translateX(-50%) translateX(${-6 * win(t, 3.6, 4.6)}vw) scale(${0.92 + 0.08 * win(t, 0, 1)})`;
      }

      // 2. the scale, alone: its pans sway; the page lands on the right pan, which sinks under it
      stage(scale, t, 4.4, 8.1, V(0, -1.3, 0));
      scale.rotation.y = Math.sin(now * 0.3) * 0.25;
      const weight = win(t, 6.0, 6.6) * (1 - win(t, 7.6, 8.2));
      beam.rotation.z = Math.sin(now * 1.6) * 0.06 * (1 - weight) - 0.3 * weight;
      for (const p of pans) p.h.rotation.z = -beam.rotation.z;

      // 3. the book, alone: the page lands on it and its pages fan open
      stage(book, t, 8.8, 13.4, V(0, -1.1, 0));
      book.rotation.set(0.35, -0.25 + Math.sin(now * 0.4) * 0.08, 0);
      fan.forEach((h, k) => { h.rotation.z = win(t, 10.3 + k * 0.08, 11.4 + k * 0.08) * (1 - win(t, 12.4, 13.2)) * (0.25 + k * 0.38); });

      // THE PAGE: where it is in each part of the film
      pans[1].anchor.getWorldPosition(pt);
      const onPan = pt.clone().add(V(0, 0.08, 0));
      const onBook = V(book.position.x + 0.15, book.position.y + 0.62, book.position.z + 0.25);
      const behind = V(0.1, 1.2, -2), out = V(-2.4, 2.8, 2), floating = V(0, 1.0, 1.6);
      let pos, rest = 0, restRot = null;
      if (t < 1.2) pos = behind;                                                          // hidden behind the statue
      else if (t < 3.4) pos = bezier(behind, V(-1.0, 4.2, 0.5), out, win(t, 1.2, 3.4));   // comes out and flies
      else if (t < 6.0) pos = bezier(out, V(-0.8, 4.8, 1.5), onPan, win(t, 3.4, 6.0));    // to the scale
      else if (t < 7.8) { pos = onPan; rest = 1; restRot = [-Math.PI / 2, 0, 0]; }        // on the pan
      else if (t < 10.3) pos = bezier(onPan, V(3.2, 4.4, 2), onBook, win(t, 7.8, 10.3));  // to the book
      else if (t < 13.4) { pos = onBook; rest = 1; restRot = [-Math.PI / 2 + 0.35, 0, -0.25 + Math.sin(now * 0.4) * 0.08]; }
      else pos = bezier(onBook, V(0, 1.6, 1.2), floating, win(t, 13.4, 14.4));            // lifts and floats
      if (t >= 14.4) pos = floating.clone().add(V(0, Math.sin(now * 1.1) * 0.06, 0));
      paper.position.copy(pos);
      paper.visible = t > 1.0 && t < 22.6;
      paper.scale.setScalar((t < 13.4 ? 0.75 : 0.75 + 0.45 * win(t, 13.4, 14.4)) * (1 - win(t, 22, 22.6)));
      const floatW = win(t, 13.4, 14.4);
      if (rest) paper.rotation.set(...restRot);
      else if (floatW > 0) paper.rotation.set(-0.15 * floatW + (1 - floatW) * (-Math.PI / 2 + 0.35), Math.sin(now * 0.6) * 0.15, 0);
      else paper.rotation.set(-0.9 + Math.sin(now * 3) * 0.5, Math.sin(now * 1.3) * 0.8, Math.sin(now * 2.2) * 0.4);
      bend(rest ? 0.04 : floatW > 0 ? 0.12 + 0.6 * (1 - floatW) : 0.9, now);

      // 4. the magnifying glass: golden light gathers into it, then it slides across the page
      const glassAt = V(-0.55 + 1.1 * win(t, 15.4, 17.4), 1.15 + Math.sin(now * 2) * 0.04, 2.3);
      const gIn = win(t, 14.8, 15.3), gOut = win(t, 17.6, 18.3);
      glass.visible = gIn > 0.001 && gOut < 0.999;
      glass.scale.setScalar(Math.max(0.001, gIn) * (1 + 0.15 * Math.sin(Math.PI * gIn)));
      glass.position.copy(glassAt).add(V(3 * gOut, 2.5 * gOut, 0));
      glass.rotation.set(0, (1 - gIn) * 2.5, 0);
      glow.material.opacity = 0.9 * win(t, 15.6, 16.1) * (1 - win(t, 17.6, 18.3));

      // 5. the check: the light gathers into the page, it glows, a gold check rises out of it
      const rise = win(t, 19.2, 20.0) * (1 - win(t, 22, 22.6));
      check.visible = rise > 0.001;
      check.scale.setScalar(Math.max(0.001, rise) * 1.15);
      check.position.set(floating.x, floating.y + 0.1 + rise * 0.55, floating.z + 0.5);
      check.rotation.set(0, (1 - rise) * Math.PI * 2 + Math.sin(now * 0.8) * 0.25, 0);
      paperMat.emissiveIntensity = 0.5 * win(t, 18.6, 19.2) * (1 - win(t, 19.8, 20.8));

      // the swirl of light: gathers for the glass (14.2-15.2), gathers for the check (18.3-19.2), then bursts
      const target = t < 18 ? glassAt : floating;
      if (t > 14.2 && t < 15.3) { gather(target, (t - 14.2) / 1.0, now); swirlMat.opacity = Math.min(1, (t - 14.2) * 3); }
      else if (t > 18.3 && t < 19.2) { gather(target, (t - 18.3) / 0.9, now); swirlMat.opacity = Math.min(1, (t - 18.3) * 3); }
      else if (t > 19.2 && t < 21.2) { burst(check.position, t - 19.2); swirlMat.opacity = 1 - (t - 19.2) / 2; }
      else swirlMat.opacity = 0;
      const fl = [15.2, 19.2].map((a) => t - a).find((d) => d > -0.25 && d < 0.6);   // a flash and a ring of light
      flash.material.opacity = fl !== undefined ? Math.max(0, 1 - Math.abs(fl - 0.05) / 0.5) : 0;
      flash.scale.setScalar(fl !== undefined ? 1.5 + (fl + 0.25) * 4 : 1);
      flash.position.copy(target);
      ring.material.opacity = fl !== undefined && fl > 0 ? 0.9 * (1 - fl / 0.6) : 0;
      ring.scale.setScalar(fl !== undefined && fl > 0 ? 1 + fl * 2.6 : 1);
      ring.position.copy(target);

      const p = Math.max(0, PARTS.filter((s) => t >= s).length - 1);
      if (p !== lastPart) { lastPart = p; setPart(p); }
      renderer.render(scene, camera);
    };
    frame();

    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); io.disconnect();
      scene.traverse((o) => { o.geometry?.dispose(); if (o.material) { o.material.map?.dispose(); o.material.dispose(); } });
      pmrem.dispose(); renderer.dispose(); host.removeChild(renderer.domElement);
    };
  }, []);

  const sc = scenes[part];
  const words = sc.title.split(" ");
  return (
    <section className={`st3d part-${part}`} ref={mount} aria-label="What Verdicta does">
      <img ref={statueImg} className="st3d-statue" src={statue} alt="" aria-hidden="true" />
      {/* the text changes with each scene; the buttons under it stay where they are */}
      <div className="st3d-left">
      <div className="st3d-text" key={part} aria-live="polite">
        {part === 0 ? <span className="lp-kicker">U.S. Supreme Court research, verified</span> : <span className="st3d-n">{part}.</span>}
        <h1>
          {words.map((w, k) => (
            <span key={k} className={`st3d-w ${(sc.accent ?? [words.length - 1]).includes(k) ? "accent" : ""}`}
                  style={{ animationDelay: `${0.15 + k * 0.08}s` }}>{w}</span>
          ))}
        </h1>
        <p className="st3d-p">{sc.text}</p>
      </div>
      <p className="lp-cta st3d-cta">
        <Link to="/research" className="lp-button">Try a question</Link>
        <a href="#weigh" className="lp-button ghost">How it works ↓</a>
      </p>
      <p className="lp-coverage st3d-coverage">{coverage}</p>
      </div>
      <div className="st3d-bar" aria-hidden="true">
        {scenes.map((s2, k) => <i key={s2.title} className={k < part ? "done" : k === part ? "on" : ""}
          style={{ "--d": `${(PARTS[k + 1] ?? LOOP) - PARTS[k]}s` }} />)}
      </div>
    </section>
  );
}
