This is a typological ontology, it is not a taxonomy. It does not have fillers like domain and class, and it does not prescribe a minimum or maximum segment count per element.

Root types: `code`, `document`, `media`, `data`, `upstream`, `downstream`

Rules:

1. For each dotted part, the address in the namespace must be reversible and read as its full name: the segments in the namespace can be reversed by replacing periods with spaces to read properly as an inferenceable, well understood name, and children must take their parent's name as their last name when reversed and read as a noun.
2. Namespace entries must describe the type of functional approach as a proper noun using Industry-Standard Lexicon, Grounded Nomenclature, and Non-Coinage: All elements, segment identifiers, compound tokens, and resulting reversed noun phrases must use the established, standard terminology recognized by practitioners who work directly with that class of artifact. Abstract pattern labels, bespoke synonyms, internal shorthand, colloquial phrases, and marketing terms are strictly prohibited. Where an authoritative or formally standardized term does not exist, the segment must use the plain, common noun for what the thing functionally is or does in ordinary practice. Never coin, invent, or adapt a term under any circumstances.
3. Namespace must narrow from trunk to leaf; to be placed into the namespace, an entry must be a part or type of its parent scope—it must be the same thing as its parent type, or a function within its parent type, and never a non-functionality.
4. Multi-word names: when the new leaf is a variant functionality of its parent type, such as physics engine and game engine, express the namespace with periods between the segments: code.engine.game, code.engine.physics. Every prefix is a complete type that yields its own inference and passes its practices to its children, so words that form a valid prefix of their own must remain separate segments. Words may be joined with underscores in one segment only when none of them forms a valid prefix, as in code.queue.dead_letter and data.bill_of_materials, where the name must also read correctly once reversed.
5. functional_name: reverse the segments of the address, then replace periods and underscores with spaces. The functional name must be the leading words of the result and should count as its acceptable short name that is well understood. (code.queue.dead_letter → dead_letter.queue.code → "dead letter queue code". "dead letter queue" passes.)
6. name: This field must always hold the name used to reference the namespace element and must NOT match the functional name, the name used in the official documentation or the commonly used term. Priority should be given to the branded or canonical name in the documentation, or its creator gave it, or a product name. (Example: Unreal Engine when it is the upstream.code.engine.game)

Examples of reading an address:

- `code.loop.main`: main loop program code
- `code.bus.data.event`: event data bus code

Examples of namespace validity:

- `code.game`: valid. Acting as a game is the primary functionality of the project
- `code.game.engine`: invalid. reverses to 'engine game', a subject/genre variant (a game about engines) rather than a recognized functional type — the same non-functionality basis that invalidates platformer; also sits under the already-invalid code.game parent.
- `code.game.fps`: invalid. invalid as a functional subtype of game as a function; it defines the fundamental challenge and objective of a first person shooter game.
- `upstream.code.engine.game`: valid. A 'game engine' is a functional type because it provides the runtime a game runs on (the main loop, rendering, input, and simulation) independent of any particular game's genre or content, and it is widely known by that exact name, upstream is valid when the game engine is not part of this project
- `code.engine.game.fps`: valid. a distinct functionality built onto an engine and is present in this project as an extension of a game engine (proof: first-person camera viewpoint with a targeting reticle, named as a subtype of the engine)
- `code.engine.game.platformer`: invalid. invalid as a functional subtype; it defines the fundamental challenge and objective of a game, not a technical functionality (proof: spatial navigation and overcoming environmental obstacles) (note: load-bearing invalid example)
- `media.image`: valid. images are a base valid functional type under the media root.
- `media.asset.image`: valid. Images are assets when they are named as a functional element type in a AUE.
- `media.photo`: valid. Photos have defining elements, and sometimes supportive elements, a couple (DE) at the eiffel tower (SE), a car (DE) in the street, a car (DE) racing at the racetrack (SE), a photo of the grand canyon (DE) in the distance a man and a mule (SE)
- `media.photo.scenery`: valid. This is function of an encounter. A representation of a scene as the DE, a scenery photo has a subject that isnt the DE, all scenes have a subject but the scene is the focus
- `media.photo.jpg`: invalid. this is encoding
- `code.cpp`: invalid. this is language
- `document.word.story.conflict`: invalid. 'word' is naming an encoding and does not name a functional approach at the proper namespace level
- `document.story.conflict`: valid. represents story conflict as a document element
