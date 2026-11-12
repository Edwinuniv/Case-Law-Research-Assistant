// The chain as a short 3D film that plays by itself (Three.js, real moving objects, no video file):
// a scale whose pans go up and down -> THE PAGE drops on a pan, lifts off and flies, bending in the air ->
// it lands on an open book whose pages fan -> a magnifying glass slides across it -> a gold check rises
// out of it -> the gavel strikes twice. Then it loops. The headline changes with each part.
// Every object is built from simple shapes here (cylinders, boxes, a torus, an extruded check).
// It stops drawing when off screen; for visitors who ask for less motion it shows one still frame.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import "./story3d.css";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const LOOP = 21;                                         // seconds for the whole film
const PARTS = [0, 4, 7.5, 10.5, 13.5, 16.5];             // start time of each of the 6 chapters
const clamp = (x) => Math.min(1, Math.max(0, x));
const ease = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const win = (t, a, b) => ease((t - a) / (b - a));        // 0 before a, 1 after b, smooth in between

function paperTexture() {                                // THE PAGE: cream paper, grey lines, a gold edge
  const c = document.createElement("canvas"); c.width = 512; c.height = 700;
  const g = c.getContext("2d");
  g.fillStyle = "#efe3c6"; g.fillRect(0, 0, 512, 700);
  g.strokeStyle = "#c9a24d"; g.lineWidth = 10; g.strokeRect(5, 5, 502, 690);
  g.fillStyle = "rgba(90,80,70,.45)";
  for (let y = 80; y < 640; y += 30) g.fillRect(56, y, (y % 150 === 80 ? 260 : 400) - Math.random() * 40, 9);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export default function Story3D({ scenes, statue, coverage }) {
  const mount = useRef(null);
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
    const camBase = new THREE.Vector3(0, 2.6, 12);

    scene.add(new THREE.AmbientLight(0xffffff, 0.22));
    const key = new THREE.DirectionalLight(0xffb347, 3.4); key.position.set(4, 7, 6); scene.add(key);
    const rim = new THREE.DirectionalLight(0xff7a1a, 2.6); rim.position.set(-6, 3, -4); scene.add(rim);

    const gold = new THREE.MeshStandardMaterial({ color: 0xd9a441, metalness: 1, roughness: 0.25 });
    const bronze = new THREE.MeshStandardMaterial({ color: 0xb06a32, metalness: 1, roughness: 0.32 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1d1d22, metalness: 0.6, roughness: 0.45 });
    const leather = new THREE.MeshStandardMaterial({ color: 0x4a2814, metalness: 0.1, roughness: 0.6 });
    const pages = new THREE.MeshStandardMaterial({ color: 0xeadcbc, roughness: 0.8 });
    const wood = new THREE.MeshStandardMaterial({ color: 0x5a2f17, metalness: 0.15, roughness: 0.4 });
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
        const a = (k / 3) * Math.PI * 2, end = new THREE.Vector3(Math.cos(a) * 0.68, -1.6, Math.sin(a) * 0.68);
        const c = mesh(new THREE.CylinderGeometry(0.012, 0.012, end.length(), 6), gold, h, end.x / 2, end.y / 2, end.z / 2);
        c.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.clone().normalize());
      }
      const bowl = new THREE.LatheGeometry([new THREE.Vector2(0, -0.18), new THREE.Vector2(0.45, -0.15),
        new THREE.Vector2(0.66, -0.05), new THREE.Vector2(0.7, 0)], 64);
      mesh(bowl, new THREE.MeshStandardMaterial({ color: 0xc98a45, metalness: 1, roughness: 0.22, side: THREE.DoubleSide }), h, 0, -1.6, 0);
      const anchor = new THREE.Object3D(); anchor.position.set(0, -1.62, 0); h.add(anchor);
      return { h, anchor };
    });

    // ---------- THE PAGE: a bendable sheet ----------
    const paperGeo = new THREE.PlaneGeometry(1.25, 1.7, 24, 24);
    const flat = paperGeo.attributes.position.array.slice();
    const paper = mesh(paperGeo, new THREE.MeshStandardMaterial({ map: paperTexture(), roughness: 0.85, side: THREE.DoubleSide }), scene);
    const bend = (amount, time) => {                       // the sheet waves like paper in the air
      const p = paperGeo.attributes.position.array;
      for (let v = 0; v < p.length; v += 3) {
        const x = flat[v], y = flat[v + 1];
        p[v + 2] = amount * (Math.sin(x * 2.6 + time * 5) * 0.22 + Math.sin(y * 1.8 - time * 4) * 0.16 + x * x * 0.2);
      }
      paperGeo.attributes.position.needsUpdate = true; paperGeo.computeVertexNormals();
    };

    // ---------- the open book ----------
    const book = group();
    for (const side of [-1, 1]) {
      const half = group(book); half.rotation.z = side * -0.12;
      mesh(new THREE.BoxGeometry(1.9, 0.08, 2.6), leather, half, side * 0.98, 0, 0);
      mesh(new THREE.BoxGeometry(1.8, 0.32, 2.45), pages, half, side * 0.95, 0.2, 0);
    }
    mesh(new THREE.BoxGeometry(4.1, 0.55, 2.8), leather, book, 0, -0.42, 0);   // a second, closed book under it
    mesh(new THREE.BoxGeometry(4.0, 0.03, 2.7), gold, book, 0, -0.14, 0);
    const fan = [];
    for (let k = 0; k < 7; k++) {                          // loose pages hinged at the spine, fanning open
      const hinge = group(book); hinge.position.y = 0.38;
      const sheet = mesh(new THREE.PlaneGeometry(1.75, 2.35), new THREE.MeshStandardMaterial({ color: 0xf1e6cc, roughness: 0.8, side: THREE.DoubleSide }), hinge, 0.88, 0, 0);
      sheet.rotation.x = -Math.PI / 2;
      fan.push(hinge);
    }

    // ---------- the magnifying glass ----------
    const glass = group();
    mesh(new THREE.TorusGeometry(0.62, 0.07, 24, 64), gold, glass);
    mesh(new THREE.CircleGeometry(0.6, 48), new THREE.MeshPhysicalMaterial({ color: 0xfff3d6, metalness: 0, roughness: 0.05,
      transmission: 0.9, transparent: true, opacity: 0.35, thickness: 0.2 }), glass);
    const handle = mesh(new THREE.CylinderGeometry(0.07, 0.09, 1.3, 24), wood, glass, 0.95, -0.95, 0);
    handle.rotation.z = Math.PI / 4;
    mesh(new THREE.TorusGeometry(0.085, 0.025, 12, 24), gold, glass, 0.52, -0.52, 0).rotation.y = Math.PI / 2;
    glass.rotation.x = -Math.PI / 2.4;
    const glow = mesh(new THREE.PlaneGeometry(1.0, 0.09), new THREE.MeshBasicMaterial({ color: 0xffb347, transparent: true, opacity: 0, blending: THREE.AdditiveBlending }), paper, 0, 0.1, 0.01);

    // ---------- the gold check ----------
    const chk = new THREE.Shape();
    chk.moveTo(-0.55, 0.05); chk.lineTo(-0.35, 0.25); chk.lineTo(-0.12, 0.0); chk.lineTo(0.5, 0.75);
    chk.lineTo(0.68, 0.55); chk.lineTo(-0.12, -0.38); chk.closePath();
    const check = mesh(new THREE.ExtrudeGeometry(chk, { depth: 0.16, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.04, bevelSegments: 4 }),
      new THREE.MeshStandardMaterial({ color: 0xf2b545, metalness: 1, roughness: 0.18, emissive: 0x6b3a00, emissiveIntensity: 0.6 }), scene);

    // ---------- the gavel ----------
    const gavel = group();
    const block = mesh(new THREE.CylinderGeometry(0.9, 1.0, 0.32, 64), wood, gavel, 0, 0.16, 0);
    mesh(new THREE.TorusGeometry(0.95, 0.03, 12, 64), gold, block, 0, 0.1, 0).rotation.x = Math.PI / 2;
    const arm = group(gavel); arm.position.set(1.9, 0.72, 0);                   // the pivot is at the end of the handle
    mesh(new THREE.CylinderGeometry(0.08, 0.1, 2.1, 24), wood, arm, -1.05, 0, 0).rotation.z = Math.PI / 2;
    const head = mesh(new THREE.CylinderGeometry(0.34, 0.34, 1.15, 48), wood, arm, -2.0, 0, 0);
    head.rotation.x = Math.PI / 2;                                             // the head lies across the handle
    for (const dy of [-0.32, 0.32]) mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.12, 48), gold, head, 0, dy, 0);
    const ring = mesh(new THREE.RingGeometry(0.9, 1.0, 64), new THREE.MeshBasicMaterial({ color: 0xffb347, transparent: true, opacity: 0,
      side: THREE.DoubleSide, blending: THREE.AdditiveBlending }), gavel, 0, 0.34, 0);
    ring.rotation.x = -Math.PI / 2;

    // ---------- sparks ----------
    const N = 260, sparkPos = new Float32Array(N * 3), sparkVel = [];
    for (let k = 0; k < N; k++) sparkVel.push(new THREE.Vector3((Math.random() - 0.5) * 2, Math.random() * 2.2 + 0.5, (Math.random() - 0.5) * 2));
    const sparkGeo = new THREE.BufferGeometry(); sparkGeo.setAttribute("position", new THREE.BufferAttribute(sparkPos, 3));
    const sparkMat = new THREE.PointsMaterial({ color: 0xffc34d, size: 0.07, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false });
    scene.add(new THREE.Points(sparkGeo, sparkMat));
    const sparksAt = (origin, age) => {
      for (let k = 0; k < N; k++) {
        const v = sparkVel[k];
        sparkPos[k * 3] = origin.x + v.x * age; sparkPos[k * 3 + 1] = origin.y + v.y * age - 1.2 * age * age; sparkPos[k * 3 + 2] = origin.z + v.z * age;
      }
      sparkGeo.attributes.position.needsUpdate = true;
    };

    // ---------- the beam of light that arrives from the statue ----------
    // (the statue stands at the top right; the beam goes from her scales down to the 3D scale)
    const beamLight = mesh(new THREE.CylinderGeometry(0.03, 0.3, 7, 24, 1, true), new THREE.MeshBasicMaterial({ color: 0xffc061,
      transparent: true, opacity: 0, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false }), scene, 2.6, 4.4, -1);
    beamLight.rotation.z = -0.85;

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

    const show = (g, a) => { g.visible = a > 0.001; g.scale.setScalar(Math.max(0.001, a)); };
    const pt = new THREE.Vector3();
    const clock = new THREE.Clock();
    let raf, lastPart = -1;

    const frame = () => {
      raf = requestAnimationFrame(frame);
      if (!visible) return;
      const now = window.__st3dTime ?? clock.getElapsedTime();   // __st3dTime: only set by our recording script, to film frame by frame
      const t = still ? 15 : now % LOOP;

      // 1. the scale arrives, the beam of light lands on it, its pans sway
      const scaleIn = win(t, 0, 1.2) * (1 - win(t, 5.5, 7));
      show(scale, scaleIn); scale.position.set(-win(t, 5.5, 7) * 6, -1.2, 0); scale.rotation.y = Math.sin(now * 0.3) * 0.3;
      beamLight.material.opacity = 0.32 * win(t, 0.2, 0.9) * (1 - win(t, 1.6, 2.6));
      const weight = win(t, 2.6, 3.4) * (1 - win(t, 4.6, 5.4));                 // the page weighs the right pan down
      beam.rotation.z = Math.sin(now * 1.6) * 0.06 * (1 - weight) - 0.3 * weight;
      for (const p of pans) p.h.rotation.z = -beam.rotation.z;

      // 2-3. THE PAGE: falls on the right pan, lifts off, flies, lands on the book
      pans[1].anchor.getWorldPosition(pt);
      const onPan = pt.clone().add(new THREE.Vector3(0, 0.05, 0));
      const bookTop = new THREE.Vector3(0.2, 0.15, 0.2);
      const fall = win(t, 1.0, 2.7), lift = win(t, 4.4, 7.2);
      const sky = new THREE.Vector3(onPan.x + 0.5, 6.5, 0.5);
      const mid = new THREE.Vector3(-1.5, 4.2, 2.5);
      let pos;
      if (t < 4.4) pos = sky.clone().lerp(onPan, fall);
      else {                                                    // a curved flight (quadratic Bezier) from the pan to the book
        const u = 1 - lift; pos = onPan.clone().multiplyScalar(u * u).add(mid.clone().multiplyScalar(2 * u * lift)).add(bookTop.clone().multiplyScalar(lift * lift));
      }
      paper.position.copy(pos);
      const flying = (t > 0.8 && t < 2.7) || (t > 4.4 && t < 7.2);
      const flat01 = t >= 7.2 ? 1 : t >= 2.7 && t <= 4.4 ? 1 : 0;
      paper.rotation.set(-Math.PI / 2 + (flying ? Math.sin(now * 3) * 0.5 : 0), flying ? now * 0.8 : 0, flying ? Math.sin(now * 2.2) * 0.4 : 0);
      bend(flying ? 0.9 : flat01 ? 0.05 : 0.3, now);
      paper.visible = t > 0.8 && t < 20.2;
      const paperScale = t < 7.2 ? 0.7 : 1.15;
      paper.scale.setScalar(paperScale * (1 - win(t, 19.6, 20.2)));

      // 3. the book rises in, its pages fan, then settle
      const bookIn = win(t, 5.8, 7.2) * (1 - win(t, 19.6, 20.6));
      show(book, bookIn); book.position.set(t > 16.5 ? 1.1 * win(t, 16.5, 17.3) : 0, -1.1, 0);
      book.rotation.set(0.35, -0.25 + Math.sin(now * 0.4) * 0.08, 0);
      fan.forEach((h, k) => { const open = win(t, 6.6 + k * 0.08, 7.8 + k * 0.08) * (1 - win(t, 9.2, 10.2)); h.rotation.z = open * (0.25 + k * 0.38); });
      if (t >= 7.2) { paper.position.set(book.position.x + 0.15, book.position.y + 0.62, 0.25); paper.rotation.set(-Math.PI / 2 + 0.35, 0, -0.25 + Math.sin(now * 0.4) * 0.08); }

      // 4. the magnifying glass slides across the page; a line lights up under it
      const glassIn = win(t, 10.3, 11) * (1 - win(t, 13.2, 13.8));
      show(glass, glassIn);
      const sweep = win(t, 10.8, 13);
      glass.position.set(paper.position.x - 0.5 + sweep * 1.0, paper.position.y + 0.9 + Math.sin(now * 2) * 0.05, 0.6);
      glow.material.opacity = 0.9 * win(t, 11.2, 11.8) * (1 - win(t, 13.6, 14.2));

      // 5. the gold check rises out of the page, with sparks
      const rise = win(t, 13.6, 14.6) * (1 - win(t, 19.6, 20.2));
      check.visible = rise > 0.001;
      check.scale.set(rise * 1.1, rise * 1.1, rise * 1.1);
      check.position.set(paper.position.x - 0.05, paper.position.y + 0.15 + rise * 0.55, 0.5);
      check.rotation.set(-0.2, -0.35 + Math.sin(now * 0.8) * 0.15, 0);
      const sAge = t - 13.7;
      sparkMat.opacity = sAge > 0 && sAge < 2 ? 1 - sAge / 2 : 0;
      if (sAge > 0 && sAge < 2) sparksAt(check.position, sAge);

      // 6. the gavel comes in and strikes twice; the camera shakes, a ring spreads
      const gavelIn = win(t, 16.5, 17.3) * (1 - win(t, 19.8, 20.6));
      show(gavel, gavelIn); gavel.position.set(-1.9, -1.25, 0.6); gavel.rotation.y = 0.5;
      // up = how high the gavel is raised: it rises slowly, then slams down fast on each strike
      const up = (at) => win(t, at - 0.9, at - 0.35) * (1 - win(t, at - 0.12, at));
      arm.rotation.z = -0.8 * (t < 18.4 ? up(18.0) : up(19.0));
      const hit = [18.0, 19.0].map((a) => t - a).find((d) => d >= 0 && d < 0.6);
      ring.material.opacity = hit !== undefined ? 0.8 * (1 - hit / 0.6) : 0;
      ring.scale.setScalar(hit !== undefined ? 1 + hit * 4 : 1);
      const shake = hit !== undefined ? (1 - hit / 0.6) * 0.06 : 0;
      camera.position.set(camBase.x + (Math.random() - 0.5) * shake, camBase.y + (Math.random() - 0.5) * shake, camBase.z);
      camera.lookAt(0, 0.6, 0);

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
      <img className="st3d-statue" src={statue} alt="" aria-hidden="true" />
      <div className="st3d-text" key={part} aria-live="polite">
        {part === 0 ? <span className="lp-kicker">U.S. Supreme Court research, verified</span> : <span className="st3d-n">{part}.</span>}
        <h1>
          {words.map((w, k) => (
            <span key={k} className={`st3d-w ${(sc.accent ?? [words.length - 1]).includes(k) ? "accent" : ""}`}
                  style={{ animationDelay: `${0.15 + k * 0.08}s` }}>{w}</span>
          ))}
        </h1>
        <p className="st3d-p">{sc.text}</p>
        <p className="lp-cta">
          <Link to="/research" className="lp-button">Try a question</Link>
          <a href="#weigh" className="lp-button ghost">How it works ↓</a>
        </p>
        {part === 0 && <p className="lp-coverage">{coverage}</p>}
      </div>
      <div className="st3d-bar" aria-hidden="true">
        {scenes.map((s2, k) => <i key={s2.title} className={k < part ? "done" : k === part ? "on" : ""}
          style={{ "--d": `${(PARTS[k + 1] ?? LOOP) - PARTS[k]}s` }} />)}
      </div>
    </section>
  );
}
