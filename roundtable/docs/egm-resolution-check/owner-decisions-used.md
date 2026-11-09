# Owner decisions made on 2026-11-07 (this session), not all yet in the map

Each line is the owner's decision. Quotes are the owner's own words.

1. JEV gets the owner's three gate questions exactly, with no TRUE/FALSE criteria: "You cant send jev two opposite statements".
   - "Does the new message add something previously unstated, or express a position on a recently raised matter?"
   - "Does the new message move the discussion forward and help answer the question?"
   - "Does the new message address the subject being discussed?"
2. A gate passes at 70%. "60 was trying to push through the faulty wording."
3. The JEV model is "~typesafe/jev-latest".
4. The topic sameness question is "{{foo}} is the same as {{bar}}". "Same underlying intent" gave too much leeway and let agents smuggle decisions into topics.
5. The owner's evaluation spec applies: three gates plus value and auditability scores at 3.0 or more, a feedback prefix with bands, no credits.
6. No "You have N Characters to Respond" line.
7. No length limit by default. If a limit is set, a message over it is blocked, never truncated: "we arent going to be truncating if we add limits in we will block messages for being too long".
8. 10 rounds by default. Each turn starts with the round count: "Round 1 of 10", and near the end "3 Rounds Remain", "2 Rounds Remain", "1 Round Remains", "Final Round".
9. With 10 rounds there is no need to end on two rounds of no good input: "we have a bound so that thats fine".
10. Unlimited rounds is a mode. "unlimited must have some kind of end though like no more good input or all agents state done." The wording for "done" is not decided.
11. Topics are off by default: "default is no topics its just the sent in prompt". "we can keep topics in the code just not by default we need to refine that a bit."
12. Remove the credits message from the participant prompt.
13. Agents are not told about passing: "I wouldnt even tell agents they get shit for passing or even mention passing honestly." "being told nothing produced the best results."
14. No timeouts, and agents are never killed for running long: "the other model created timeouts which was never meant to be the design, it also had agents being aborted if they were up and running more than 5 minutes". "if you start an agent on a task it typically runs until completion."
15. If fewer than two agents are available, the loop halts or waits until at least two are available to debate. Agents must not sit passing back and forth.
16. Messages read like normal chat, "AgentName: <message>", and keep the ID ("[R1-2]") so agents can reference messages.
17. No "reply with your contribution" / "PASS" instructions in the prompt.
18. Messages must be logically coherent, convey full thoughts, and be free of jargon and outside references, so the owner can read and interact: "the intent is for me to be able to interact with them and when I cant follow I cant interact". "plus it makes the roundtable actually able to be read and understood and not just a ball of cryptic wasted tokens."
19. README.md: "that was never my spec." Whether the README is the owner's spec is open. The owner's documents are Roundtable_ACP_Integration_Design.md, the evaluation spec, and the owner statements in the map.
20. Who moderates does not matter: "I am the moderator jev is the moderator whatever, does it matter who."
21. Gate Burden standard (Vivi) applies only to inference gates: "This only relates to inference". Only the owner removes gates.
22. Owner texts (prompts, JEV questions, feedback) are used verbatim. Changes to them need the owner.
23. Carried from 2026-11-05 (in the map): JEV is optional and its failure never halts the table.
