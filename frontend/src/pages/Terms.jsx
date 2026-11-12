// Terms of use and disclaimer (Edwin, 2026-11-12): a research aid, not legal advice; what it covers; fair use.
// The limits quoted here are the real ones: 10 questions a minute per address (app/api.py, step 5.12),
// 3 contact messages per address in 10 minutes (app/api_site.py).
import { Link } from "react-router-dom";
import SitePage from "./SitePage.jsx";

export default function Terms() {
  return (
    <SitePage kicker="Using Verdicta" title="Terms of" accent="use" updated="12 November 2026">
      <div className="sp-card sp-note">
        <strong>Verdicta is a research aid, not legal advice.</strong> It helps you find and read what U.S. Supreme Court
        decisions say. It does not know your situation and is not a lawyer. For a legal problem, ask a qualified lawyer.
      </div>

      <h2>What Verdicta covers</h2>
      <p>Answers come only from U.S. Supreme Court opinions filed from 2000 to 2024, taken from CourtListener (see{" "}
        <Link to="/sources">sources and licences</Link>). It does not cover other courts, other countries, state law,
        decisions outside those years, or anything that is not in the text of the decisions.</p>

      <h2>How to read an answer</h2>
      <ul>
        <li>Every sentence of an answer cites the passage it comes from, and every citation is checked before it is
          shown. Open the passage and read it: the passage, not the summary, is what the Court said.</li>
        <li>A <strong>low confidence</strong> answer is only partly supported: check the passages before relying on it.</li>
        <li><strong>Not supported by the retrieved opinions</strong> means the decisions we searched do not answer the
          question. It does not mean the answer is "no".</li>
        <li>An answer can still be incomplete, or miss a later decision or another opinion in the same case. Always check
          the full decision, for example on CourtListener.</li>
        <li>Each question is answered on its own: earlier questions are not used.</li>
      </ul>

      <h2>Fair use</h2>
      <ul>
        <li>Up to 10 questions a minute from one address, and 3 contact messages in 10 minutes.</li>
        <li>Do not send automated or repeated requests, try to get around the limits or the security of the site, or use
          it to harm others.</li>
        <li>Do not type personal or confidential information in a question (see the <Link to="/privacy">privacy
          policy</Link>).</li>
      </ul>

      <h2>No guarantee</h2>
      <p>Verdicta is a student project of ESIB, Université Saint-Joseph. It is provided as it is, without any guarantee
        that it is complete, correct or available. We are not responsible for decisions taken on the basis of its
        answers.</p>

      <h2>The court decisions</h2>
      <p>The decisions come from CourtListener's bulk data, which is free of known copyright restrictions (Public Domain
        Mark). The answers' wording is written by a language model and checked by our code.</p>
    </SitePage>
  );
}
