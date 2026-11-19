// Privacy policy (Edwin, 2026-11-12). Every statement here describes what the code really does:
// query_log (app/db.py), the session cookie (app/main.py), the limits per IP address kept in memory only
// (app/api.py, app/api_site.py), contact_messages (app/api_site.py), Groq (app/llm.py), Railway (deployment).
// If the code changes what is collected or kept, this page must change with it.
import { Link } from "react-router-dom";
import SitePage from "./SitePage.jsx";

export default function Privacy() {
  return (
    <SitePage kicker="Your data" title="Privacy" accent="policy" updated="19 November 2026">
      <div className="sp-card sp-note">
        <strong>In short:</strong> you do not need an account to use Verdicta. We keep the questions typed on the research
        page and the messages sent through the contact form, but no name, no IP address and no browser information with
        your questions. If you choose to create an account, we keep your email address and link your questions to it, so
        you can find them again. We use one necessary cookie, no trackers and no advertising. Please do not type personal
        information in a question.
      </div>

      <h2>Who we are</h2>
      <p>Verdicta is a student project of the École Supérieure d'Ingénieurs de Beyrouth (ESIB), Université Saint-Joseph,
        built by Yasser Hajj Youssef, Edwin Mouawad and Joe Bou Karam. You can reach us through the <Link to="/contact">contact
        page</Link>.</p>

      <h2>What we collect</h2>
      <ul>
        <li><strong>Your questions.</strong> Each question typed on the research page is saved with its result: the answer
          that was shown, the passages that were found, the status (answered, low confidence, not supported) and how long it
          took. We use this log to measure the system, to see which questions it could not answer, and to improve it.
          It is not linked to your name or your IP address. Without an account it is not linked to you at all; if you are
          logged in to your own account, it is saved with that account so that you see it again under "My questions".</li>
        <li><strong>Contact messages.</strong> If you use the contact form, we save your name, your email address and your
          message, so that we can answer you.</li>
        <li><strong>Accounts.</strong> If you sign up, and for the team's administrator accounts, we keep the email address,
          a hashed password (never the password itself) and the failed login attempts, to lock an account after repeated
          failures. Signing up asks for no name. Only your own account can see your list of questions; the team's
          administrators can see every question in the log, as for visitors without an account.</li>
        <li><strong>Activity log of an account.</strong> For each account we keep a dated list of what it did: sign-up,
          logins and failed logins, logouts, questions, and requests refused by a limit. The team's administrators can
          read it and download it, to run and improve the site; every action of an administrator is itself recorded in a
          separate log. No IP address and no password are kept in these logs, and an account's log is deleted with it.</li>
        <li><strong>The paid plan.</strong> If you upgrade, you type your card details on Stripe's own payment page, never on
          ours. We keep only the two identifiers Stripe gives us (your customer record and your subscription), so that the
          subscription can be cancelled: no card number and no amount. Payments run in Stripe's test mode: no real money
          moves.</li>
        <li><strong>Forgot password.</strong> If you ask for a new password, we keep a scrambled copy (a hash) of the
          link we email you, for 30 minutes at most, and delete it once it is used. The page says the same thing whether
          an account exists or not.</li>
      </ul>

      <h2>What we do not collect</h2>
      <ul>
        <li>We do not save your IP address. The server uses it only for a short time, in memory, to limit how many
          questions (10 a minute), logins, new accounts (5 an hour) and contact messages (3 in 10 minutes) come from one
          address.</li>
        <li>We do not save your browser or device information.</li>
        <li>We use no analytics, no advertising and no tracking. The pages load no script or font from another website,
          except the login and sign-up pages, which load Google's sign-in button when "Continue with Google" is
          offered.</li>
      </ul>

      <h2>The one cookie</h2>
      <p>The site sets a single session cookie. It holds a security token that protects every form from requests sent by
        other websites, and, if you are logged in, your login. It is signed, cannot be read by the page's scripts, is sent
        only over HTTPS on the live site and expires after 8 hours. It is necessary for the site to work, so we do not ask
        for consent to it.</p>

      <h2>Who receives your question</h2>
      <ul>
        <li><strong>Groq</strong>, the provider that runs the language model: each question is sent to it, with the
          passages of the court decisions that were found, so that the model can draft the answer. Groq's own privacy
          policy applies to that request.</li>
        <li><strong>Railway</strong>, which hosts the website and its database.</li>
        <li><strong>Google</strong>, only on the login and sign-up pages: its sign-in button is loaded from Google, so
          Google sees that visit. If you continue with Google, Google gives us your email address and nothing else is
          kept (no Google password or token).</li>
        <li><strong>Stripe</strong>, only if you choose the paid plan: it receives your email address and what you type on
          its payment page. Stripe's own privacy policy applies to that payment.</li>
        <li><strong>Resend</strong>, only if you ask for a new password: it delivers that one email, so it receives your
          email address and the link.</li>
      </ul>
      <p>We do not sell or share your questions or messages with anyone else.</p>

      <h2>How long we keep them</h2>
      <p>Questions, accounts and contact messages are kept with no fixed deletion date. Questions asked without an account
        are not linked to you, so we cannot find them by your name. If you want your account (with its questions) or a
        contact message deleted, write to us from the email address concerned and we will delete it.</p>

      <h2>Changes</h2>
      <p>If what we collect changes, we will update this page and its date.</p>
    </SitePage>
  );
}
