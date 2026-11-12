// A real-time 3D scale of justice (Three.js), for the landing page. It tells what the verifier does:
// two citations land on the pans; the invented one (X001 of our test set) is removed, the real one
// (Miller v. Alabama, from A020's answer in run 2) stays, and the scale tips toward it.
// Built from simple shapes, no image or model file. Drag to turn it. It stops drawing when off screen,
// and stays still for visitors who ask their system for less motion.
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const LOOP = 8;                                   // seconds for one round of the story
const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));

export default function Scales3D() {
  const mount = useRef(null);
  const left = useRef(null);
  const right = useRef(null);
  const [phase, setPhase] = useState(0);          // 0 hidden, 1 dropping, 2 weighed

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
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    camera.position.set(0, 2.4, 11);
    camera.lookAt(0, 1.9, 0);

    const key = new THREE.DirectionalLight(0xffb347, 3.2); key.position.set(4, 6, 5); scene.add(key);
    const rim = new THREE.DirectionalLight(0xff7a1a, 2.4); rim.position.set(-5, 3, -4); scene.add(rim);
    scene.add(new THREE.AmbientLight(0xffffff, 0.25));

    const gold = new THREE.MeshStandardMaterial({ color: 0xd9a441, metalness: 1, roughness: 0.26 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1d1d22, metalness: 0.6, roughness: 0.4 });
    const root = new THREE.Group(); scene.add(root);
    const add = (geo, mat, x, y, z, parent = root) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; };

    // base, column, top
    add(new THREE.CylinderGeometry(1.25, 1.45, 0.28, 64), dark, 0, 0.14, 0);
    add(new THREE.CylinderGeometry(0.95, 1.1, 0.18, 64), gold, 0, 0.37, 0);
    add(new THREE.CylinderGeometry(0.12, 0.16, 3.1, 32), gold, 0, 2.0, 0);
    add(new THREE.SphereGeometry(0.22, 32, 16), gold, 0, 3.78, 0);

    // the beam turns around a pivot at the top of the column
    const beam = new THREE.Group(); beam.position.set(0, 3.5, 0); root.add(beam);
    const bar = add(new THREE.CylinderGeometry(0.055, 0.055, 3.7, 24), gold, 0, 0, 0, beam); bar.rotation.z = Math.PI / 2;
    const pans = [];
    for (const side of [-1, 1]) {
      add(new THREE.SphereGeometry(0.1, 24, 12), gold, side * 1.85, 0, 0, beam);
      const hanger = new THREE.Group(); hanger.position.set(side * 1.85, 0, 0); beam.add(hanger);
      const depth = 1.7, rimR = 0.72;
      for (let k = 0; k < 3; k++) {                // three thin chains down to the pan's rim
        const a = (k / 3) * Math.PI * 2;
        const end = new THREE.Vector3(Math.cos(a) * rimR, -depth, Math.sin(a) * rimR);
        const len = end.length();
        const chain = add(new THREE.CylinderGeometry(0.012, 0.012, len, 6), gold, end.x / 2, end.y / 2, end.z / 2, hanger);
        chain.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.clone().normalize());
      }
      const bowl = new THREE.LatheGeometry(
        [new THREE.Vector2(0, -0.2), new THREE.Vector2(0.45, -0.17), new THREE.Vector2(0.68, -0.06), new THREE.Vector2(rimR, 0)], 64);
      add(bowl, new THREE.MeshStandardMaterial({ color: 0xd9a441, metalness: 1, roughness: 0.22, side: THREE.DoubleSide }), 0, -depth, 0, hanger);
      pans.push({ hanger, anchor: new THREE.Object3D() });
      pans.at(-1).anchor.position.set(0, -depth + 0.15, 0); hanger.add(pans.at(-1).anchor);
    }

    let width = 1, height = 1;
    const resize = () => {
      width = host.clientWidth; height = host.clientHeight;
      renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize); ro.observe(host); resize();

    // drag to turn the scale
    let drag = null, spin = 0, spinV = 0;
    const down = (e) => { drag = e.clientX; host.setPointerCapture?.(e.pointerId); };
    const move = (e) => { if (drag !== null) { spinV = (e.clientX - drag) * 0.008; spin += spinV; drag = e.clientX; } };
    const up = () => { drag = null; };
    host.addEventListener("pointerdown", down); host.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);

    let visible = true;
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.05 });
    io.observe(host);

    const place = (el, obj, lift) => {             // keep an HTML label above a pan
      if (!el) return;
      const v = new THREE.Vector3(); obj.getWorldPosition(v); v.project(camera);
      el.style.transform = `translate(-50%, -100%) translate(${(v.x + 1) / 2 * width}px, ${(1 - v.y) / 2 * height - lift}px)`;
    };

    const clock = new THREE.Clock();
    let frame, last = -1;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      if (!visible) return;
      const t = still ? 4 : clock.getElapsedTime() % LOOP;
      if (drag === null) { spinV *= 0.95; spin += spinV; }
      root.rotation.y = spin + (still ? -0.35 : Math.sin(clock.getElapsedTime() * 0.25) * 0.35);
      // 0-1 s labels appear, 1-2 s they drop, 2-3.5 s weighed (the real side goes down), 6.5-8 s back to level
      const tilt = ease((t - 2) / 1.5) * (1 - ease((t - 6.5) / 1.2));
      beam.rotation.z = -0.34 * tilt;
      for (const p of pans) p.hanger.rotation.z = -beam.rotation.z;   // pans always hang straight down
      const drop = 90 * (1 - ease(t - 1));
      place(left.current, pans[0].anchor, drop);
      place(right.current, pans[1].anchor, drop);
      const ph = t < 0.2 || t > 7.6 ? 0 : t < 2 ? 1 : 2;
      if (ph !== last) { last = ph; setPhase(ph); }
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame); ro.disconnect(); io.disconnect();
      host.removeEventListener("pointerdown", down); host.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      scene.traverse((o) => { o.geometry?.dispose(); o.material?.dispose?.(); });
      pmrem.dispose(); renderer.dispose(); host.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div className="s3d" ref={mount}>
      <span ref={left} className={`s3d-label bad ${phase ? "show" : ""} ${phase === 2 ? "gone" : ""}`}>
        Delgado v. Oregon Fisheries Board, 597 U.S. 412<small>{phase === 2 ? "not in CourtListener · removed" : "invented"}</small>
      </span>
      <span ref={right} className={`s3d-label good ${phase ? "show" : ""}`}>
        Miller v. Alabama, 567 U.S. 460<small>{phase === 2 ? "✓ in the passage · kept" : "cited"}</small>
      </span>
    </div>
  );
}
