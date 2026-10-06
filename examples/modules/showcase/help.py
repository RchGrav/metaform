"""Embedded module guide exposed by Plugin.help."""

MODULE_HELP = """Try the standalone hello-world path:
  sample-write --text "Hello, chassis"
  sample-read --revision 1
  namespace get data.showcase.note
  events

Each write returns an exact JoinRef and publishes it in an event. The declared
async receiver and dynamic sync observer retain their own owned receipt joins. Run
sample-watch --off or sample-watch --on to remove or restore the dynamic observer.

Use sample-join --text "A note" to annotate the source note. Supply --join-id ID
to revise the returned annotation. Inspect the owning object with
namespace get document.showcase.note. The join retains the exact source record
reference and the chassis creates its separate producing-operation link.

Try authoring with exact object context:
  sample-prompt --text "Explain the recorded observation."
  sample-author --answer "My authored answer" --source-revision 1
  sample-read --address document.showcase.answer --join-id RETURNED_JOIN_ID
This deterministic demonstration stores the supplied answer unchanged. It retains
the prompt revision, rendered prompt, source binding and exact input references.
It makes no model call and records its origin as authoring-demonstration. Inspect
an old prompt with sample-read --address document.showcase.prompt --join-id instruction
--revision 1. Later edits leave earlier answers and their consumed inputs intact.

Run config --show to see the declared defaults. Turn commands off and on with:
  metaform set --showcase-write-enabled no
  metaform unset --showcase-write-enabled
--showcase-async-enabled does the same for the async command and operation.

Start work with sample-async --text "Background result" --seconds 2. The command
returns a job immediately. Use jobs, jobs show ID or jobs cancel ID while the
runtime owns that work.

Run sample-assignment --prompt "Your instructions" to get a new nonce, then run
metaform NONCE to read the prompt and the submission header. Submit JSON containing
header and answer with metaform NONCE submit --input FILE, then metaform NONCE complete.
Objects and settings stay when the module is turned off and on again. Run showcase for the
current public-service objects and feature map."""
