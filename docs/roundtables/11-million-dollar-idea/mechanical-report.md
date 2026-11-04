# Roundtable 11: 3d2b2f99-million-dollar-idea

This report was written from the table's record alone, by no model. The table ended because every topic was discussed, synthesized, ranked, explained and summarized.

Opening: A person brings you a question. It is the whole frame of this discussion: it is not about one part of anything unless it says so, and it may be about something that does not exist yet.

The question: Million dollar idea

You are in the folder of the person's project, and you can read its files when the question touches it. You cannot change anything, and nothing you say changes the project; the person reads the table's report and decides. Build on what the others contribute, add what only you can add, and keep going until the question is answered.

## Seats

- Opus (acp:claude/opus): 7 slots, 6 submissions, 6 kept, active
- Astra (acp:codex/gpt-6-astra): 7 slots, 6 submissions, 6 kept, active
- Sol (acp:codex/gpt-6.1-sol): 7 slots, 6 submissions, 6 kept, active
- Fable (acp:claude/fable): 7 slots, 6 submissions, 6 kept, active

## Topic 1: Million dollar idea

### Ideas, as Opus synthesized them

I1. Fixed-price technical due-diligence audit (base proposal): Sell Metaform's blindspot critic as a $20k fixed-price audit for acquirers and investors. It would ingest the target's repo, build the functional model, and report gaps in the stated purposes (missing functions or Encounters) with evidence for each. Fifty audits make $1M, so developers don't need to adopt the platform first, and each audit tests the model on someone else's code. Human DD firms take weeks for the same work.
I2. Claim-to-evidence audit with a paid pilot: Narrow the audit to the seller's five claims that matter most to the deal. Trace each to code, tests and operational evidence, and separate claims that are contradicted from claims that can't be verified. A human technical reviewer is included. Sell one paid pilot before building more. The acceptance test is whether a finding changes the buyer's diligence plan, valuation assumptions or contract protections.
I3. White-label evidence appendix through boutique DD firms: Distribute through technical diligence firms as a paid, white-label appendix on one live deal. The partner supplies buyer access and human review. Measure reviewer hours saved, findings adopted and delivery cost. This tests whether firms buy the tooling repeatedly even if investors buy full audits only occasionally. The early risks are whether partners allow code access and whether the price leaves a margin.
I4. Self-audit of Metaform as the first sales artifact: A grounding note: the critic is a spec (LAYER-014, open questions in D103), not a shipped tool. So the first audit should be run on Metaform itself, by hand if necessary, and used as the sales artifact. Opus objected that a report on Metaform written by its own author won't persuade a buyer.
I5. Rights to an anonymised findings corpus: The service revenue is not the durable asset. The asset is the corpus of claim-to-evidence findings across many repos, so pilot contracts should keep rights to anonymised findings. Opus started a warning about this right, but the contribution was cut off.
I6. Historical backtest on public repos: Run the audit on public repos at the commit before a documented failure, such as a breach or a claimed feature that didn't work, and show whether it flagged the problem. That gives buyers checkable evidence and tests the critic before anyone pays. Astra objected that models may already know about public incidents (hindsight leakage).
I7. Sealed benchmark on a partner's private completed audit: Give the critic only the evidence available at the time and keep the human findings sealed until scoring. Reviewers also assess any new findings. Measure material misses, false alarms and review time. Opus said this wrongly assumes a partner will donate the data. Astra's fix is a pilot discount in exchange for an authorised sealed benchmark case.
I8. Cheap-baseline comparison: Compare against a reviewer using code search and a general-purpose model on the same time budget. Score verified, decision-relevant findings per total delivery hour, including setup and false-alarm cleanup. If the baseline does as well, sell the service with existing tools and defer building the critic.
I9. Score by finding type and price by edge: Score the sealed test by finding type. A general model will probably match Metaform on "does feature X exist." Metaform's possible edge is purpose-level gaps, which only show up once the whole repo is mapped. If the edge is limited to that structural class, price the audit as a module inside the partner's report and make the money on volume.
I10. R&W insurance underwriters as buyer and data source: Sell to underwriters of representations-and-warranties insurance in M&A. They price risk on seller claims every week, and their past claim files could serve as a sealed test set with known outcomes. Astra cautioned that a claim file is only useful if it links a covered loss to a defect detectable in pre-underwriting evidence, which may lack a repo snapshot. Check that chain on one case with one underwriting sponsor before changing buyers.
I11. Paid remediation follow-up for repeat revenue: Within the first deal, offer a separately priced follow-up that verifies whether the top findings were fixed, reusing the evidence links and acceptance tests. If buyers purchase it, that supports a recurring verification business. If not, the economics must work as an episodic service. Sol also pointed out that 50 audits says nothing about the cost of winning 50 customers.
I12. Seller-side MCP tool as a lead channel: Metaform is specced as an MCP server (06-mcp-install.md), so target engineers could run the critic during pre-sale prep. Each seller run becomes a lead for the buyer-side audit on the same deal. Opus objected that this is a conflict: sellers won't pay for a tool that feeds the buyer's audit, and serving both sides undermines buyer trust.
I13. Vendor due diligence / seller readiness review: Sell only to sellers, as vendor DD: one seller-paid report goes to every bidder, and bidders' questions show which findings matter. Astra added safeguards against selective disclosure: - agree the claim list, evidence scope and repo snapshot in advance; - keep unresolved findings, access limits and verified fixes in the final report; - give bidders reproducible checks for a sample of claims; - include a repair-and-retest window. Sol proposed testing it through one sell-side adviser, who offers the same fixed-price review to three clients preparing a sale. Track purchases, days to repo access and delivery hours.
I14. Post-close live-map handoff to the acquirer: The map built for the seller's report is the map the acquirer needs on day one for integration. Sell continued access after close to whoever ends up owning the code: one report, two payers at different times. Astra warned this crosses a budget line, because deal teams buy diligence and engineering buys integration tools. Test a separately priced 90-day handover tied to one task, such as mapping dependencies before consolidating systems, with a named owning team, and count demand only when it pays.
I15. Liability and adviser-signed reports: In vendor DD, bidders usually get reliance letters, so one missed defect could cost more than all fees earned. Professional-liability insurance is unlikely for an unproven AI method, so the reports would have to go out under a signing adviser. Sol said these claims were unverified. Opus agreed they came from general practice rather than anything checked, so the pilot should test them, including whether an adviser will adopt a finding after checking its evidence and how long that takes.
I16. Verify-not-reinvestigate deliverable: MAP-043 requires every conclusion to reference the exact files behind it. So deliver each finding with its evidence and a reproduction step, and measure minutes per adopted finding. A low number makes the liability constraint cheap to satisfy. A high number means the adviser is doing the real work and the product is only a lead list.
I17. Coverage statement with an independent boundary: Liability comes from what is missing, so signers should sign off on scope. Metaform's address map would mark every element as examined or not (Opus). Astra warned that this needs an independent denominator: if the map omits a subsystem, it can still report 100%. Reconcile it against a separately supplied inventory of repos, deployed services, interfaces and seller claims, and keep "evidence unavailable" separate from "checked, no issue found." Fable added that MAP-041 keeps the boundary explicit, so the boundary declaration should be a deliverable the seller signs, not something Metaform infers.
I18. Capacity and unit-economics test: At $20k, $1M means about one completed audit per week. At 40 delivery hours each, that is 2,000 hours before sales, access setup, revisions or support. Log all founder and reviewer time in the pilot to decide between raising the price, delivering faster or hiring, and to see whether the million leaves a profit.
I19. Boundary-and-coverage template as the product: Fable expects the hours that don't scale to be boundary negotiation and access setup, not the critic's run. If the pilot log confirms this, the product to sell advisers is a boundary-and-coverage template, with the critic as the engine behind it.

### Rankings, best first

Opus: I13, I2, I8, I7, I16, I17, I18, I1, I3, I15, I9, I11, I10, I14, I19, I6, I5, I12, I4

Astra: I2, I3, I8, I18, I17, I13, I7, I16, I11, I9, I1, I14, I4, I19, I6, I15, I10, I5, I12

Sol: I2, I3, I8, I13, I18, I17, I7, I16, I11, I9, I4, I14, I1, I19, I15, I6, I5, I10, I12

Fable: I13, I2, I8, I17, I16, I18, I3, I7, I9, I1, I15, I11, I19, I5, I14, I10, I6, I12, I4

### Borda count (derived)

Derived: a Borda count over the rankings that were read (of n ideas, first earns n - 1 points, last none). The raw rankings are the record; nothing in the protocol depends on this.

I2. Claim-to-evidence audit with a paid pilot: 70 points
I8. Cheap-baseline comparison: 64 points
I13. Vendor due diligence / seller readiness review: 64 points
I3. White-label evidence appendix through boutique DD firms: 56 points
I17. Coverage statement with an independent boundary: 55 points
I18. Capacity and unit-economics test: 54 points
I7. Sealed benchmark on a partner's private completed audit: 50 points
I16. Verify-not-reinvestigate deliverable: 50 points
I9. Score by finding type and price by edge: 36 points
I1. Fixed-price technical due-diligence audit (base proposal): 34 points
I11. Paid remediation follow-up for repeat revenue: 34 points
I15. Liability and adviser-signed reports: 24 points
I14. Post-close live-map handoff to the acquirer: 23 points
I19. Boundary-and-coverage template as the product: 20 points
I4. Self-audit of Metaform as the first sales artifact: 14 points
I6. Historical backtest on public repos: 12 points
I10. R&W insurance underwriters as buyer and data source: 12 points
I5. Rights to an anonymised findings corpus: 10 points
I12. Seller-side MCP tool as a lead channel: 2 points

### Top three, as each seat explained them

Opus: **I13, vendor due diligence / seller readiness review.** This is the business model that most of the other ideas depend on.
- **Conflict:** the seller pays and the report goes to every bidder. That removes the conflict that sinks I12, where one tool serves both sides of a deal.
- **Repeat sales:** one engagement reaches many buyers, which eases the acquisition-cost worry Sol raised.
- **Existing market:** vendor DD is already a paid category, so the pitch is "the same deliverable, faster and with evidence attached," not "trust a new kind of report."
- **Safeguards:** Astra's additions (scope agreed in advance, unresolved findings kept in, reproducible checks for bidders, a retest window) answer the obvious objection that seller-paid reports are selective.
- **Testability:** Sol's test with three clients through one adviser costs little and gives a clear answer.

**I2, claim-to-evidence audit with a paid pilot.** This turns an open-ended "find gaps" service into a fixed scope that can actually be delivered: five claims, each traced to evidence, with "contradicted" kept separate from "can't verify."
- **Built-in demand test:** the acceptance test (did a finding change the diligence plan, the valuation or the contract terms?) measures whether someone pays for a consequential decision, not whether the output impressed them.
- **Sequencing:** selling one pilot before building more fits the fact that the critic is still a spec (LAYER-014), not a shipped tool.

**I8, cheap-baseline comparison.** This is the test that can save the most wasted effort.
- **The open question:** none of the other ideas show that Metaform's functional model adds anything over a reviewer with code search and a general-purpose model.
- **Low cost:** if the baseline does as well, you still have a service business without building the critic first.
- **Supports the others:** it is the control that makes the results of I7 (sealed benchmark) and I9 (score by finding type) meaningful.

**Why these three rank above the rest:** together they settle wh

Astra: 1. **I2: Claim-to-evidence audit with a paid pilot.** It turns a broad, unfinished capability into a bounded offer: investigate five consequential claims, show the evidence, and distinguish contradictions from uncertainty. A paid pilot tests both willingness to pay and whether the findings affect a real decision. It can start with substantial manual work, so building the critic need not precede learning whether the business deserves investment. The $20k price remains a hypothesis.

2. **I3: White-label evidence appendix through boutique DD firms.** It offers a plausible route to customers, authorised evidence, and expert review through one relationship. An appendix also gives the partner a small, concrete deliverable to evaluate within its existing process. Repeat purchases could support a business even when individual acquisition buyers purchase infrequently. Access, partner interest, and margins remain unproven, but a live pilot can test them together.

3. **I8: Cheap-baseline comparison.** It addresses the most consequential technical uncertainty: whether Metaform’s functional model earns its additional complexity. Comparing verified findings per total delivery hour captures setup, review, and false-alarm costs. If ordinary search and a general model perform equally well, the service might still succeed while investment in the critic should wait.

Together, these establish the offer, the route to market, and the justification for proprietary technology. Coverage statements and evidence packaging strengthen delivery. Follow-ups, subscriptions, and findings corpora depend on first proving that someone buys useful work at a sustainable cost.

Sol: 1. **I2: Claim-to-evidence audit with a paid pilot.** It connects a bounded deliverable to a consequential buyer decision. Five agreed claims give the review a manageable scope, while separating contradictions from missing evidence prevents overstating findings. Payment tests demand before substantial development. I ranked it above the broad $20k audit because its scope and success criteria are easier to evaluate.

2. **I3: White-label appendix through diligence firms.** It addresses customer access and reviewer trust, two problems technical accuracy alone cannot solve. A partner could supply live transactions, review expertise, and repeat purchases. The pilot tests those assumptions through adopted findings, hours saved, and margin. It offers a concrete distribution experiment with fewer new assumptions than entering insurance underwriting or selling post-close integration tools.

3. **I8: Cheap-baseline comparison.** It tests whether building Metaform’s critic is worth the additional effort. A useful report could come from skilled consulting with existing tools. Comparing verified findings per total delivery hour reveals whether the functional model improves the economics. If it does, there is evidence to justify development. If it does not, the paid service might still work.

These three resolve demand, distribution, and technical advantage. Coverage controls, reproducible evidence, and capacity checks remain necessary, but cannot establish those three foundations by themselves.

Fable: **I13 first** because it is the only go-to-market that resolves the three blockers the discussion surfaced at once. Access: the seller owns the code, so no partner has to donate a private audit or sealed data. Conflict: one payer, one side, so buyer trust is intact. Liability: the report goes out through the sell-side adviser, who already signs vendor DD reports, so the unverified insurance question becomes the adviser's problem rather than a solo author's. Astra's safeguards (pre-agreed claim list, snapshot, retained unresolved findings, reproducible checks) make it defensible, and Sol's three-client test through one adviser is a cheap, repeatable way to learn the acquisition cost that I1's "50 audits" skips over. It also leaves room for I14 and I11 later without redesign.

**I2 second** because it is the correct first step regardless of which channel wins. Narrowing to five deal-critical claims shrinks delivery hours (Sol's capacity problem), and the acceptance test, did a finding change the buyer's plan, valuation, or contract terms, is the only metric in the list that measures willingness to pay rather than technical accuracy. Separating "contradicted" from "unverifiable" is also what makes the later coverage statement (I17) honest.

**I8 third** because it is the test most likely to kill or validate the whole premise. The critic is still a spec in the repo, not a shipped tool, so the real question is whether building it is worth it. A reviewer with code search and a general model on the same time budget is the honest comparator; if it matches Metaform on verified, decision-relevant findings per delivery hour, the service can be sold now with existing tools and the critic deferred. If Metaform wins only on purpose-level gaps (I9), that tells you how to price and position. Either outcome is actionable, which most of the other ideas are not until this one is answered.

The common thread: each of these converts a belief into something a single pilot can measure, and together they sequence as pilot design (I2), v

### Bottom three, as each seat explained them

Opus: **I4, self-audit of Metaform as the first sales artifact.** Running the critic on Metaform by hand is fine for development. As a sales artifact it proves nothing: the author audits their own code, written in the model's own vocabulary, with no independent ground truth. A buyer can't tell skill from self-confirmation. I6 (backtest) and I7 (sealed benchmark) produce evidence a buyer could actually check.

**I12, seller-side MCP tool as a lead channel.** It sells to both sides of the same deal. Sellers won't pay for runs that become leads for the buyer's audit, and buyers lose trust in findings from a vendor the seller already paid. I13 keeps the seller-side insight without the conflict.

**I5, rights to an anonymised findings corpus.** The long-term logic is sound, but deal NDAs and seller confidentiality usually forbid keeping findings. Asking for those rights in a first pilot adds friction to the sale that matters most. The plan should work without the corpus. Treat it as a bonus if a client agrees, not as th

Astra: - **I10: Insurance underwriters.** This requires several unproven links: covered losses must correspond to detectable technical defects, historical evidence must exist, and insurers must permit access and pay for screening. A sponsor could validate these, but the proposal adds uncertainty before the simpler diligence offer has a customer.

- **I5: Anonymised findings corpus.** Retaining findings does not establish their commercial value. Findings may depend heavily on repository context, and negotiating reuse rights could obstruct early sales. Build a corpus only after identifying a specific improvement it enables and obtaining suitable permission.

- **I12: Seller runs as buyer leads.** It creates a trust problem at the point where sellers must grant sensitive access. Sellers need control over disclosure and a clear benefit from any referral. MCP compatibility helps delivery but provides no evidence that this acquisition channel works. Seller readiness reviews offer a cleaner incentive.

Sol: - **I5:** It assumes retained findings become a valuable asset before showing that they improve future audits. Negotiating reuse rights adds confidentiality friction to the first sale. Corpus value should follow demonstrated usefulness.

- **I10:** This requires several unproven links: access to claim files, matching historical repository evidence, and findings that influence underwriting decisions. It introduces a new buyer and a harder validation problem before the simpler diligence offer has been tested.

- **I12:** MCP compatibility makes a tool accessible but does not establish demand. Turning seller-side runs into buyer-side leads also creates competing incentives: sellers may want private remediation before disclosure. The proposal leaves consent, independence, and customer acquisition unresolved.

Fable: **I4 last** because it was my own suggestion and Opus's objection holds: a report on Metaform by Metaform's author proves nothing to a buyer, and running the critic "by hand" on a spec that does not yet exist produces an artifact that is neither evidence of the method nor of the product. Its only residual value is as a grounding note that the critic is unbuilt, which I17 and I19 already carry.

**I12 next** because the conflict Opus named is fatal, not fixable. A seller will not pay for a tool whose runs become leads for the party negotiating against them, and a buyer who learns the audit vendor also served the seller discounts every finding. I13 keeps the useful part, seller-side distribution via MCP, without the two-sided trap.

**I6** because hindsight leakage makes the result unfalsifiable: a hit on a well-known breach could be recall rather than detection, and a sceptical buyer will say so. The sealed private benchmark (I7) tests the same thing without that hole, so I6 adds risk without adding informatio

### Host summary by Opus

# Summary: model rankings for "Million dollar idea"

## Overall picture

The four models agree on how to proceed: start with a small paid pilot, test whether the critic beats cheap tools, and leave the expansion ideas for later. They split on one question, which is the route to customers. Opus and Fable prefer selling to sellers through vendor due diligence (I13). Astra and Sol prefer selling through boutique DD firms (I3).

## Average position across the four rankings

| Tier | Ideas (average rank) |
|---|---|
| **Most favored** | I2 claim-to-evidence pilot (1.5) · I8 cheap baseline (3.0) · I13 vendor DD (3.0) |
| **Strong support** | I3 white-label appendix (5.0) · I17 coverage statement (5.25) · I18 unit economics (5.5) · I7 sealed benchmark (6.5) · I16 verify-not-reinvestigate (6.5) |
| **Middle** | I9 score by finding type (10.0) · I1 base audit (10.5) · I11 remediation follow-up (10.5) |
| **Low** | I15 liability/adviser-signed (13.0) · I14 post-close handoff (13.25) · I19 boundary template (14.0) · I4 self-audit (15.5) |
| **Least favored** | I6 public backtest (16.0) · I10 R&W underwriters (16.0) · I5 findings corpus (16.5) · I12 seller MCP lead channel (18.5) |

## Top-three selections and reasons

**I2 (claim-to-evidence pilot) is in every model's top two.** Astra and Sol ranked it first; Opus and Fable ranked it second. Their reasons were consistent:
- It turns an open-ended "find gaps" service into five claims that can actually be delivered.
- Keeping "contradicted" separate from "can't verify" avoids overstating findings. Fable added that this is what makes I17's coverage statement honest.
- The acceptance test asks whether a finding changed the diligence plan, the valuation or the contract terms. That measures willingness to pay rather than technical accuracy.
- Selling one paid pilot first suits the fact that the critic is still a spec (LAYER-014). Astra noted the first pilot can be largely manual.
- Sol ranked it above I1 because its scope and success criteria are easier to evaluate.

**I8 (cheap-baseline comparison) was ranked third by all four.** This was the only unanimous placement. Every model called it the test of whether building Metaform's critic is worth it:
- Measuring verified findings per total delivery hour includes setup and false-alarm cleanup.
- If the baseline does as well, the service can still be sold with existing tools, so the result is useful either way.
- Opus and Fable said it is the control that makes I7 and I9 meaningful. Fable linked a narrow win on purpose-level gaps directly to I9's pricing logic.

**I13 (vendor DD) was ranked first by Opus and Fable.** Both argued it resolves several blockers at once:
- **Conflict:** one payer on one side keeps buyer trust intact, which is the problem that sinks I12.
- **Access:** the seller owns the code, so no partner has to donate private audit data. This was Fable's point.
- **Liability:** reports go out under a sell-side adviser who already signs vendor DD reports, so I15's insurance question falls to the adviser. Also Fable's point.
- **Existing market:** vendor DD is already a paid category. Opus framed the pitch as "the same deliverable, faster and with evidence attached."
- **Acquisition cost:** one report reaches many bidders. Sol's test with three clients through one adviser is a cheap way to measure what I1's "50 audits" skips over.
- Both credited Astra's safeguards against selective disclosure.

**I3 (white-label appendix) was ranked second by Astra and Sol.** They argued:
- One partner relationship covers customer access, authorised evidence and expert review together.
- A small appendix fits into the partner's existing process.
- Repeat purchases by firms could carry the business even if individual acquirers buy rarely.
- Sol said it needs fewer new assumptions than the insurance (I10) or post-close (I14) routes.

Astra and Sol both described their top three as covering **demand, distribution and technical advantage**. Fable described its top three as a sequence: pilot design (I2), channel (I13), then technical validation (I8). Both of those explanations were cut off before the end.

## Bottom-three selections and reasons

**I12 (seller MCP lead channel) was in every model's bottom two.** It was last for Astra and Sol and second-to-last for Opus and Fable:
- Sellers won't pay for runs that become leads for the party negotiating against them.
- Buyers will discount findings from a vendor the seller has already paid. Fable called this conflict "fatal, not fixable."
- Sol added that sellers may want to fix problems privately before disclosing them.
- Astra and Sol both said MCP compatibility makes the tool accessible but doesn't show the channel works.
- Opus and Fable said I13 keeps the useful seller-side part without the conflict.

**I5 (findings corpus) was in the bottom three for Opus, Astra and Sol.**
- Deal NDAs and seller confidentiality usually forbid keeping findings. Opus raised this.
- Negotiating reuse rights adds friction to the first sale, which is the one that matters most.
- Astra and Sol said the corpus's value should be shown, by a specific improvement it enables, before it is pursued.
- Opus's explanation was cut off but treated the corpus as a possible bonus, not part of the plan.

**I10 (R&W underwriters) was in the bottom three for Astra and Sol.** Both said it depends on a chain of unproven links: covered losses must trace to detectable defects, historical repo evidence must exist, and insurers must allow access and pay. It also adds a new buyer before the simpler offer has a single customer.

**I4 (self-audit) was last for Opus and Fable.** Fable proposed this idea and ranked it last, saying Opus's objection holds. A report on Metaform written by Metaform's author proves nothing to a buyer. Running a critic that hasn't been built "by hand" also produces evidence of neither the method nor the product. Opus said I6 and I7 produce evidence a buyer can actually check.

**I6 (public backtest) was in Fable's bottom three.** Hindsight leakage means a hit could be the model remembering the incident rather than detecting it. Fable said I7 tests the same thing without that flaw.

## Agreement

- **Order of work:** all four favor a bounded paid pilot (I2) and a cheap-baseline test (I8) before building the critic.
- **Delivery safeguards are in the second tier:** coverage statements (I17), unit economics (I18), the sealed benchmark (I7) and evidence packaging (I16) all sit around 5–7. They are seen as necessary but not foundational.
- **Expansion ideas are premature:** I5, I10, I12 and I14 rank low because each adds a new buyer, a new data dependency or a trust problem before the core offer is proven.
- **The original I1 pitch is mid-table (10.5):** the models consistently preferred its narrower version, I2.

## Disagreement

- **Which channel:** I13 placed 1st, 6th, 4th and 1st (Opus, Astra, Sol, Fable). I3 placed 9th, 2nd, 2nd and 7th. Opus and Fable put the seller-paid report first. Astra and Sol put the buyer-side partner first.
- **I4 (self-audit):** Opus and Fable ranked it last, but Sol had it 11th and Astra 13th. Sol and Astra apparently saw some value in it as a development step, while the other two judged it only as a sales artifact.
- **I15 (liability):** Opus ranked it 10th and Fable 11th, while Astra and Sol had it 16th and 15th. That fits Opus and Fable's view that liability matters once vendor DD is the channel.
- **I10 (underwriters):** Opus ranked it 13th, higher than the others, who had it 16th–18th.

Several explanations were cut off: Opus's and Fable's top-three summaries, Opus's I5 reasoning and Fable's I6 reasoning. The points above use only the parts that came through.
