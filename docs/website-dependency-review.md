# Website dependency review, 2026-09-20

The website's existing lockfile pinned React, React DOM and the RSC transport to
19.2.6. A fresh installation exposed the upstream server-function denial-of-service
advisory. The three packages are updated together to **19.2.8**, the patched release
in the same minor series. Their prior package files are retained in Git and a
separate local backup. No automatic major-version audit fix was applied.

The upstream [React advisory](https://github.com/react/react/security/advisories/GHSA-wx67-qw84-cm4g)
identifies affected RSC transports and the 19.2.8 backport. Although this application
uses explicit API routes, its framework supports RSC, so the patch is appropriate;
this report does not claim an exploit was reproduced against the website.

With the patched dependencies, all 31 isolated website checks, TypeScript checking
and the production build passed. The deployed runtime and local browser checks
are recorded with the corresponding release evidence, not inferred from npm's
package classification. In particular, `react-server-dom-webpack` is declared a
development dependency but contributes to the bundled server.

The full website dependency audit still reports **13 findings: 9 high and 4
moderate**, primarily in the existing framework and development-tool dependency
trees. This patch does not certify that whole tree as clean. The interactive
PowerPoint runtime has a separate lockfile and audit result; its zero-advisory
result must not be presented as the website's result. Broad framework upgrades
are separate from this narrowly scoped transport patch.
