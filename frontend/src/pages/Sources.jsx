// Sources and licences (Edwin, 2026-11-12): where the data, the models and the main tools come from, with their
// licences. The coverage line comes from the server (GET /api/site, config.COVERAGE), not from this file.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import SitePage from "./SitePage.jsx";

export default function Sources() {
  const [site, setSite] = useState(null);
  useEffect(() => { api("/site").then(setSite).catch(() => setSite({})); }, []);
  return (
    <SitePage kicker="Where it comes from" title="Sources and" accent="licences" updated="12 November 2026">
      <h2>The court decisions</h2>
      <p>{site?.coverage ? <>Coverage: <strong>{site.coverage}</strong>. </> : null}The decisions, their texts, their
        official citations and the table of every citation come from the bulk data of{" "}
        <a href="https://www.courtlistener.com/" target="_blank" rel="noreferrer">CourtListener</a>, run by the{" "}
        <a href="https://free.law/" target="_blank" rel="noreferrer">Free Law Project</a>, a non-profit organisation.
        The data is free of known copyright restrictions (Public Domain Mark), and the licence is recorded with every
        decision when it is loaded. Each answer's passage panel links to the decision on CourtListener.</p>

      <h2>How a citation is checked</h2>
      <p>The language model never writes a citation itself: it points to a numbered passage, and Verdicta writes the
        citation from CourtListener's citation table. Every sentence then passes six checks before it is shown (the
        passages it cites, its quote, citations, case names, numbers and dates, and whose opinion it is). See{" "}
        <Link to="/">how it works</Link>.</p>

      <h2>Models and tools</h2>
      <ul>
        <li><strong>gpt-oss-120b</strong>, an open-weight language model released by OpenAI (Apache 2.0 licence), run by
          Groq: it drafts the answer from the passages found.</li>
        <li><strong>bge-small-en-v1.5</strong> by BAAI (MIT licence): finds passages by meaning.</li>
        <li><strong>Eyecite</strong> by the Free Law Project: reads legal citations in text.</li>
        <li><strong>PostgreSQL</strong> with <strong>pgvector</strong>, <strong>FastAPI</strong> and <strong>React</strong>:
          the database, the server and the pages.</li>
      </ul>

      <h2>The project</h2>
      <p>Verdicta is a student project of ESIB, Université Saint-Joseph (end-of-semester project P4), supervised by
        Georges Salloum. See the <Link to="/terms">terms of use</Link>: it is a research aid, not legal advice.</p>
    </SitePage>
  );
}
