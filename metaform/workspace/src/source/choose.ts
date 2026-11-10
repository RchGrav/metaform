// Which source the page uses: the host's routes or the simulated data.
//
// The test for "the host serves this page" is a `meta` element that only the host adds to the
// page (`HOST_MARK` in metaform/rust/crates/metaform-web/src/lib.rs). The reasons:
// - The mark is in the page itself, so the page never asks the host a question to decide. A host
//   that is slow or fails still gives the real source, and the page then shows the failure. It
//   never shows simulated data in place of a project.
// - The mark needs no build flag. The same built page uses the host when the host serves it, and
//   the simulated data when another server does, such as `npm run dev`.
// - `?mock` in the address always gives the simulated data, for a demonstration on the host.

/** The `name` of the element the host adds. Keep it the same as the host's `HOST_MARK`. */
export const HOST_MARK = "metaform-host";

/**
 * `search` is the address's query (`location.search`). `hostMark` says whether the page has the
 * host's element: `document.querySelector(`meta[name="${HOST_MARK}"]`) !== null`.
 */
export function chooseSource(search: string, hostMark: boolean): "host" | "mock" {
  if (new URLSearchParams(search).has("mock")) return "mock";
  return hostMark ? "host" : "mock";
}
