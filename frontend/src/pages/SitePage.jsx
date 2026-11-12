// The layout of the site's information pages: privacy, terms, sources, contact (Edwin, 2026-11-12).
// A dark band with the logo and the title (the accent word in italic gradient, like the landing page),
// the text in a readable column, and links between the four pages.
// The logo comes from assets/logo-seal.webp, the same file as the header and every other page.
import { Link, NavLink } from "react-router-dom";
import logoMark from "../assets/logo-seal.webp";   // the Verdicta seal (Yasser, 2026-11-12)
import "./site.css";

export const SITE_PAGES = [["/privacy", "Privacy"], ["/terms", "Terms of use"], ["/sources", "Sources & licences"],
  ["/contact", "Contact"]];

export default function SitePage({ kicker, title, accent, updated, children }) {
  return (
    <div className="sp">
      <section className="sp-hero">
        <Link to="/" className="sp-back"><span aria-hidden="true">←</span> Back</Link>   {/* to the main page (Yasser) */}
        <img className="sp-logo" src={logoMark} alt="" />
        <span className="sp-kicker">{kicker}</span>
        <h1>{title} <em>{accent}</em></h1>
        {updated && <p className="sp-updated">Last updated {updated}</p>}
      </section>
      <div className="sp-body">
        <nav className="sp-nav" aria-label="Site information">
          {SITE_PAGES.map(([to, name]) => <NavLink key={to} to={to}>{name}</NavLink>)}
        </nav>
        <article className="sp-text">{children}</article>
      </div>
    </div>
  );
}
