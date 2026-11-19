// The Verdicta logo in both versions (Edwin, 2026-11-19): the white V for dark backgrounds and the black V for
// light ones. theme.css shows the right one for the chosen appearance; the other stays hidden.
import onDark from "../assets/logo-light.webp";
import onLight from "../assets/logo.webp";

export default function Logo({ className = "" }) {
  return (
    <>
      <img src={onDark} alt="" className={`logo-on-dark ${className}`.trim()} />
      <img src={onLight} alt="" className={`logo-on-light ${className}`.trim()} />
    </>
  );
}
