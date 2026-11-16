# Specifications on the map

Status: plan, 2026-11-16. Nothing built yet.

## The problem it solves

Agents have been changing Metaform without knowing what it is or what the part in front of them is for. Two cases from
2026-11-16: a camera change slipped into the 3D map inside an unrelated commit broke dragging, and a feature built only
because the agent protocol offered it (client files and terminals, an editor's feature in a program that has no editor)
kept every agent on the protocol's old version. In both, nothing put the purpose of the part in front of the agent.

The specifications hold that purpose: each requirement record says what a part must do and why. Today they are
markdown files in `specifications/`, about 450 records, and an agent reads them only if it thinks to.

## How it works

1. **Specifications are an overlay of the map.** Each requirement record is one record of a `specifications` overlay,
   placed at the element it is about: the 3D map's layout record at the 3D view's element, the intake's records at the
   intake's element. A record keeps its id (`VIEW-005`) and its text exactly as written.
2. **They round-trip.** The files can be read into the overlay, and the overlay written back out to the files, so a
   change on either side reaches the other. Writing out what was read in gives the same files, byte for byte.
3. **An agent starting work is given the project description and the base map**: what the project is, and its parts
   with their names, roles and how they want one another, in compact form. When it works at a part, that part's
   localized view (what the element panel shows: what it wants, what wants it, its overlays) carries the
   specification records there, so it reads why the part is as it is before changing it.

## Order of work

1. **The overlay.** Define `specifications` in the project store: a record's id, title, its whole text as written,
   and the file it came from with its place in that file, so a write-out rebuilds the files in their order.
2. **Read in.** Each record of `specifications/01` to `11` is placed at the element it is about. Placing is a
   judgement: an agent reads the record and the map and proposes the element; a record about several parts is placed
   at each. The person sees the placements before they are kept.
3. **Write out.** The overlay written back to the files; a test that reading in and writing out leaves the files as
   they were.
4. **At start.** The project description and the base map in what an agent is given when it starts, and the
   specification records in the localized view at each part.
5. **Check:** an agent started on a ticket at the 3D view is shown the 3D map's layout records before it edits.

## Open

- **Where the project description lives.** The store has none: a project holds addresses, wants, overlays and its
  defining element, and an element holds its names, role, code reference and status. It could be a field of the
  project, or a record at the defining element.
- **Records about Metaform as a whole** (quality rules, the index): placed at the defining element, or kept apart.
- **Which side is edited day to day,** the files or the overlay, once both exist.
