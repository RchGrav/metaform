# VIEW-038 "When the map is drawn": the code now gives ambient animation the idle rate

Draft for Rich, from ticket code.interface.graphical#36 (performance.md F2, 2026-10-14). Nothing in `specifications/` was changed.

## How the code works now

`moving3d` and `frame3d` (`src/metaform/modules/web/page/app/map3d/graph3d.js`): the flash and pulse of a part's record, a ghost rising, an agent's figure, a lit reach and the mascot up and about (`FRAMES.busy`, set in `prepare3d`, `map3d/labels.js`) are drawn every frame until nothing has been done or changed for `web_flow_seconds` (30 s), and then 15 times a second, each at its own speed. Any act or change (`wake3d`, called by the person's acts and by agents' acts on figures) puts them back to every frame.

The 2D map's flash and pulse are CSS animations (`flash`, `glow-pulse` in `app.css`). `rest2d` in `map2d/flow2d.js` holds every infinitely repeating CSS animation under `#map2d` once the page has been left alone for the same 30 s, and steps it on 15 times a second; `wake2d`, called from every `wake3d`, lets them run again. Before, they ran at the screen's rate for as long as a record was open.

## Where VIEW-038 differs

VIEW-038's "When the map is drawn" bullet lists "while a part flashes or pulses … while … an agent moves" among the times a frame is drawn, and gives the 15-a-second idle rate only to the dots that flow along the joins. It says nothing about a flash, a ghost or a figure once the map has been idle for 30 seconds. Until this change the code drew them every frame forever, so a map with one open `trouble` record kept the graphics busy (39–49 fps, 37–39% CPU at rest).

## Proposed text

When the map is drawn: the 3D map draws a frame only while something on it moves. Something moves while the layout settles, while the camera flies or coasts, while the pointer is on the map, while a part flashes or pulses, while a wave, a part's text or an agent moves, and for a short time after any change to what is drawn. The dots that flow along the joins, VIEW-005, keep flowing, and a part's flash or pulse, a ghost rising and an agent's figure keep moving; once nothing has been done or changed for 30 seconds they are drawn 15 times a second, at their own speed, in both maps. With reduced motion nothing flows or flashes, so an idle map draws nothing.

## Not decided here

`web_idle_flow` (on by default) still keeps the flowing dots at the full frame rate after 30 seconds, as its help text says, against the 15-a-second rate VIEW-038 gives. That is performance.md F3 and is Rich's call.
