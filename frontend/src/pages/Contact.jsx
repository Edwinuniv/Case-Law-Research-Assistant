// Contact (Edwin, 2026-11-12): the team, the addresses from the settings (GET /api/site, CONTACT_EMAIL, separated by
// commas: the whole team receives the mail; not shown when empty) and a form that sends POST /api/contact with the
// CSRF token (api.js). Messages from the form are read on the admin page "Messages".
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import SitePage from "./SitePage.jsx";

const EMPTY = { name: "", email: "", message: "" };

export default function Contact() {
  const [site, setSite] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [state, setState] = useState({ busy: false, ok: "", error: "" });
  useEffect(() => { api("/site").then(setSite).catch(() => setSite({})); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function send(e) {
    e.preventDefault();
    setState({ busy: true, ok: "", error: "" });
    try {
      await api("/contact", form);
      setForm(EMPTY);
      setState({ busy: false, ok: "Thank you: your message was sent. We will answer by email.", error: "" });
    } catch (err) {
      setState({ busy: false, ok: "", error: err.message });   // e.g. a missing field, or the 3-in-10-minutes limit
    }
  }

  return (
    <SitePage kicker="Get in touch" title="Contact" accent="us">
      <p>Verdicta is built by <strong>Yasser Hajj Youssef</strong>, <strong>Edwin Mouawad</strong> and <strong>Joe Bou
        Karam</strong>, students at ESIB, Université Saint-Joseph, Beirut, supervised by Georges Salloum. Questions about
        the project, a wrong answer, a problem with the site: write to us.</p>

      {site?.contact_emails?.length > 0 && (            // one message to all of us: mailto with every address
        <div className="sp-card">
          By email, to the whole team:{" "}
          <a className="sp-mail" href={`mailto:${site.contact_emails.join(",")}`}>write to us</a>
          <ul>{site.contact_emails.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}

      <form className="sp-card sp-form" onSubmit={send}>
        <h2>Send us a message</h2>
        <label>Your name<input required maxLength={100} value={form.name} onChange={set("name")} autoComplete="name" /></label>
        <label>Your email (to answer you)<input type="email" required maxLength={200} value={form.email} onChange={set("email")}
                                                autoComplete="email" /></label>
        <label>Message<textarea required minLength={10} maxLength={5000} rows={6} value={form.message} onChange={set("message")} /></label>
        <button disabled={state.busy}>{state.busy ? "Sending…" : "Send"}</button>
        {state.ok && <p className="sp-ok" role="status">✓ {state.ok}</p>}
        {state.error && <p className="sp-err" role="alert">✕ {state.error}</p>}
        <p className="sp-small">We keep your name, email and message to answer you, with no fixed deletion
          date; ask us to delete them at any time. See the <Link to="/privacy">privacy policy</Link>.</p>
      </form>
    </SitePage>
  );
}
