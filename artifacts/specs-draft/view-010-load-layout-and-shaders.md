# Draft for the owner: VIEW-010 and the 2D layout at load (ticket 82954773, code.interface.graphical#39, 2026-10-15)

Not applied to `specifications/`. The code is the reference; this records where the built page and the records now differ.

## Differences

1. VIEW-010's Status says the "layout cache ... built or planned for that target ... were removed, 2026-09-26". The page now keeps, in the browser, the way the 2D map's fill-the-pane search chose for each base (localStorage `metaform.fit2d.<project>.<base>`). It keeps the way only, not the drawing or the positions, and it cuts nothing back: the map is drawn whole, as before.
2. VIEW-010's "How it shows: ... draws its first vertices in under a second" is still not met. Measured on the RTX 3090, the 3D map's first frame comes at 2.3-5.2 s, mostly the module graph and data (F8, T6).
3. No record says how the 3D map opens in Space at load. The page now draws ultra from its first frame when nothing is drawn yet. Before, it drew clean and faded to space through the veil once the settings were read. The fade remains for every switch the person makes.

## Proposed amendment text, for the owner's approval

- VIEW-010, Amendment, 2026-10-15, ticket 82954773: the 2D map is laid out once at load and shown, in the way this browser kept for the same map and pane, and the search for the way that fills its pane best goes on after it is shown, one layout at a time when the page is idle. The way chosen is kept in the browser for each base, so a reload lays the map out once. The 3D map's shaders are linked before the frame that first draws them, off the page's thread, and kept while the page is open; the 3D map in Space is drawn in space from its first frame.
