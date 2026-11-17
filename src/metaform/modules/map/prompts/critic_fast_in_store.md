This run is MODE A: FAST MODE.

Your critic run is {{ run }}. Write each blind spot with the project tool as one record of the challenges overlay, at the element where you see it:
  {"add": {"{{ project }}.<address>": {"challenges": [{"run": "{{ run }}", "blinded": {{ blinded }}, "challenge": "<the blind spot>"}]}}}
A blind spot about one of an element's wants is written at the element holding the want, naming the element it wants:
  {"add": {"{{ project }}.<address>": {"challenges": [{"run": "{{ run }}", "blinded": {{ blinded }}, "want": "{{ project }}.<wanted address>", "challenge": "<the blind spot>"}]}}}
A blind spot that proposes something new says in its challenge what it would add and what that would want or serve, at the element it would join; it adds nothing to the map.

The metaform:

{{ metaform }}
