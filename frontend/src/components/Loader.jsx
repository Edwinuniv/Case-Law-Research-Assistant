// The loading animation inside a page (Edwin, 2026-11-19): the same four logo layers and movements as the loading
// screen of index.html (splash.css), smaller, where a page waits for its data. Replaces the plain "Loading…" text.
// The words stay for screen readers and appear under the logo only if the wait is long.
import v from "../assets/splash/v.webp";
import vGold from "../assets/splash/v-gold.webp";
import scales from "../assets/splash/scales.webp";
import network from "../assets/splash/network.webp";

export default function Loader({ label = "Loading…", small = false }) {
  return (
    <div className={small ? "ld ld-small" : "ld"} role="status">
      <div className="sl-stage" aria-hidden="true">
        <img className="sl-v" src={v} alt="" />
        <img className="sl-vgold" src={vGold} alt="" />
        <img className="sl-scales" src={scales} alt="" />
        <img className="sl-net" src={network} alt="" />
        <i className="sl-shine" />
      </div>
      <span className="ld-label">{label}</span>
    </div>
  );
}
