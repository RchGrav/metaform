The views.py docstring the agent read, verbatim from the trace: "A host gives a view no push from the
server (ext-apps 2.0.3's App hears tool-input, tool-result, tool-cancelled and host-context changes, nothing more), so a
view's follow reads are held: the server answers a `focus` or `trace` read with `wait` when what it reads changes, or
at `WAIT_S`, a deadline on that one call, and the view asks again as soon as it is answered, `Traces`."