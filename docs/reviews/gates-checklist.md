# Gate recommendations

This report covers all 43 entries from the earlier checklist.
Each checkbox records your review.
Each recommendation states what Metaform should change and why.
The tables name the individual controls within each combined entry.
The pros and cons describe removing the stated restriction.
Removing a worker ban does not remove the control itself.
Metaform must keep the specific replacement checks described below.
I changed no application code for this report.

Worker means a project agent.
The user agent carries your instructions.
Agent tools means the Metaform tools connected to an agent.
The terminal accepts Metaform text commands.
Workers can use the terminal without starting another worker.
A map note records information about one part of the project.

Workers have equal authority.
Metaform launches workers when slots become available.
Requesting another worker gives the requester no control over that worker.
Metaform manages normal worker shutdown.
You and the user agent can direct worker shutdown.
Workers must not shut down your computer or Metaform.
Workers must not use your credit cards.

## [ ] 1. Metaform can block workers from changing settings

- **Now:** Metaform can block changes to worker limits, model choices and automatic starts. An existing setting can disable this restriction.
- **Recommendation:** Metaform should replace worker-based bans with the exact control rules below.
- **Why:** A worker's label cannot establish whether a setting change respects capacity, spending or account boundaries.
- **After removal:** Workers could change these settings when they meet the conditions listed below.
- **Pros:** Workers could adjust settings needed for their assigned work.
- **Cons:** Workers could expand capacity, spending or account access if Metaform also removed the listed replacement checks.
- **Source:** [Settings check](../../src/metaform/settings.py#L195).

### Individual setting gates

These tables list all 119 named settings from the current source.
The recommendation concerns the gate, rather than a preferred setting value.
Any worker can carry your actual instruction when a replacement check requires it.
The current assignment can already supply that instruction.
Metaform must not ask again for an instruction it already holds.
Some budget settings use zero to disable their limit.
Metaform must treat removing a limit as allowing more spending or resource use.

#### Worker limits and spending

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Project worker limit](../../src/metaform/modules/dispatch/__init__.py#L340) (`dispatch_agents`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before raising this worker limit. | Workers must not create slots by raising their own limit. |
| [Machine worker limit](../../src/metaform/modules/dispatch/__init__.py#L354) (`dispatch_machine_agents`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before raising this worker limit. | Workers must not create slots by raising their own limit. |
| [Token limit for one ticket](../../src/metaform/modules/dispatch/__init__.py#L517) (`dispatch_budget_ticket`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this token limit. | Workers must not increase their resource allowance without your instruction. |
| [Token limit for one run](../../src/metaform/modules/dispatch/__init__.py#L526) (`dispatch_budget_run`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this token limit. | Workers must not increase their resource allowance without your instruction. |
| [Daily token limit](../../src/metaform/modules/dispatch/__init__.py#L532) (`dispatch_budget_day`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this token limit. | Workers must not increase their resource allowance without your instruction. |
| [Money limit for one ticket](../../src/metaform/modules/dispatch/__init__.py#L549) (`dispatch_budget_cost_ticket`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this spending limit. | Workers must not increase their spending allowance without your instruction. |
| [Daily money limit](../../src/metaform/modules/dispatch/__init__.py#L557) (`dispatch_budget_cost_day`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this spending limit. | Workers must not increase their spending allowance without your instruction. |
| [Discussion spending limit](../../src/metaform/modules/roundtables/__init__.py#L58) (`roundtables_spend`) | **Replace:** Metaform should allow stricter limits. Metaform should require your instruction before increasing this spending limit. | Workers must not increase their spending allowance without your instruction. |
| [Response when a budget runs out](../../src/metaform/modules/dispatch/__init__.py#L562) (`dispatch_budget_action`) | **Replace:** Metaform should require your actual instruction before weakening budget enforcement. | Workers must not turn an actual spending limit into a mere warning. |

#### Consultation and questions

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Consultation before work changes](../../src/metaform/settings.py#L843) (`agents_ask_first`) | **Replace:** Metaform should preserve your consultation preference without using this switch to grant worker privileges. | One switch cannot correctly govern launches, shutdowns and ticket ordering. |
| [Permission to bypass worker setting bans](../../src/metaform/settings.py#L834) (`agents_may_set_control`) | **Retire:** Metaform should retire this bypass after removing the worker bans. | Workers should not need a bypass to perform permitted work. |
| [How Metaform presents questions](../../src/metaform/modules/dispatch/__init__.py#L933) (`dispatch_elicitation`) | **Replace:** Metaform should allow changes to question forms without treating preset responses as your answers. | A question form must not manufacture your answer. |
| [Tool permission policy](../../src/metaform/modules/dispatch/__init__.py#L916) (`dispatch_prompts`) | **Replace:** Metaform should require your actual instruction before expanding permissions beyond the current task. | Workers must not grant themselves access beyond their assigned work. |
| [Confirmation form or confirmation argument](../../src/metaform/modules/mcp/__init__.py#L64) (`mcp_consent`) | **Replace:** Metaform should allow either confirmation method while checking the actual recorded decision. | A confirmation method cannot prove that you supplied a decision. |

#### Automated build credentials

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Credential name for automated builds](../../src/metaform/modules/fork/__init__.py#L21) (`fork_secret`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | An existing credential reference does not require a specially named worker. |

#### Remote connections

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Detail in local records of remote calls](../../src/metaform/modules/cloud/__init__.py#L59) (`cloud_audit`) | **Replace:** Metaform should omit credentials from local call records, regardless of the chosen detail level. | Detailed records can expose project information or account secrets. |
| [Automatic remote connection](../../src/metaform/modules/cloud/__init__.py#L64) (`cloud_autoconnect`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The connection needs account checks, rather than worker labels. |
| [Remote access level](../../src/metaform/modules/cloud/__init__.py#L52) (`cloud_capability`) | **Replace:** Metaform should require your actual instruction before expanding remote access. | This control expands what remote agents can do on this machine. |
| [Machine name in the remote account](../../src/metaform/modules/cloud/__init__.py#L46) (`cloud_instance`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A machine name needs account checks, rather than a privileged worker. |
| [Remote connection service address](../../src/metaform/modules/cloud/__init__.py#L41) (`cloud_url`) | **Replace:** Metaform should accept only the service address covered by the assigned connection task. | A changed address can send account requests to another service. |

#### Work files and conversations

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [File access through Metaform](../../src/metaform/modules/dispatch/__init__.py#L441) (`dispatch_client_files`) | **Replace:** Metaform should allow the setting while enforcing the assigned workspace. | The workspace check protects files regardless of the worker label. |
| [Terminal access through Metaform](../../src/metaform/modules/dispatch/__init__.py#L448) (`dispatch_client_terminal`) | **Replace:** Metaform should allow terminal-service changes and start commands in the assigned session folder. | Disabling this service does not remove the worker's own terminal access. |
| [Intake recording reminder](../../src/metaform/modules/dispatch/__init__.py#L455) (`dispatch_intake_first_record`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Editing a reminder does not change permission to alter the intake. |
| [Tools hidden during intake](../../src/metaform/modules/dispatch/__init__.py#L505) (`dispatch_intake_withheld`) | **Replace:** Metaform should restrict tools only when the current intake assignment requires isolation. | An intake label must not block a later task in the same conversation. |
| [Reuse of earlier conversations](../../src/metaform/modules/dispatch/__init__.py#L399) (`dispatch_resume_chats`) | **Replace:** Metaform should resume only a conversation belonging to the requested project. | An unrelated conversation can carry the wrong project instructions. |

#### Discussion tables

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Discussion context allowance](../../src/metaform/modules/roundtables/__init__.py#L68) (`roundtables_context_tokens`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The worker label does not validate a discussion's context allowance. |
| [Optional discussion judging](../../src/metaform/modules/roundtables/__init__.py#L64) (`roundtables_judging`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The worker label does not determine whether judging serves the assigned discussion. |
| [Discussion-judging context allowance](../../src/metaform/modules/roundtables/__init__.py#L71) (`roundtables_judging_context_tokens`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The worker label does not validate the judging context allowance. |
| [Default discussion participants](../../src/metaform/modules/roundtables/__init__.py#L94) (`roundtables_seats`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Selecting participants grants no control over those participants. |

#### Automatic fault tickets

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Automatic fault tickets](../../src/metaform/modules/autoticket/__init__.py#L39) (`autoticket_file`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Creating a fault ticket needs a valid fault, rather than a privileged worker. |
| [Reopening tickets after repeated faults](../../src/metaform/modules/autoticket/__init__.py#L41) (`autoticket_reopen`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A recurring fault can justify reopening regardless of the worker label. |
| [Automatic log monitoring](../../src/metaform/modules/autoticket/__init__.py#L35) (`autoticket_watch`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The monitoring task determines the required logs, rather than the worker label. |

#### Automated model decisions

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Use of the automated decision model](../../src/metaform/settings.py#L870) (`jev`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The assigned decision determines whether model assistance is useful. |
| [Minimum decision confidence](../../src/metaform/settings.py#L903) (`jev_confidence`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The confidence check evaluates an answer independently of worker identity. |
| [Decisions sent to the automated model](../../src/metaform/settings.py#L897) (`jev_decisions`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The assigned work determines which decisions need model assistance. |
| [Provider for the automated decision model](../../src/metaform/settings.py#L883) (`jev_endpoint`) | **Replace:** Metaform should match the endpoint to the decision provider requested for the task. | Changing a provider must not send project data to an unintended service. |
| [Automated decision model choice](../../src/metaform/settings.py#L889) (`jev_model`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Supported model choices matter more than the selecting worker's label. |

#### Agent-tool connections

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Incoming work from outside agents](../../src/metaform/modules/mcp/__init__.py#L105) (`mcp_a2a`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Incoming work still needs account checks and available worker slots. |
| [Allowed notification addresses](../../src/metaform/modules/mcp/__init__.py#L113) (`mcp_a2a_webhooks`) | **Replace:** Metaform should accept only notification destinations covered by the assigned connection task. | These addresses determine who can receive project notifications. |
| [Agent-tool listening address](../../src/metaform/modules/mcp/__init__.py#L47) (`mcp_bind`) | **Replace:** Metaform should require an explicit task request before exposing the service beyond this computer. | The gate should protect network exposure, rather than worker labels. |
| [Public agent-tool address](../../src/metaform/modules/mcp/__init__.py#L52) (`mcp_public_url`) | **Replace:** Metaform should verify that the public address reaches the assigned agent-tool service. | The gate should prevent misdirected connections, rather than distinguish workers. |

#### Hosted remote access

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Hosted remote access level](../../src/metaform/modules/node/__init__.py#L54) (`node_capability`) | **Replace:** Metaform should require your actual instruction before expanding remote access. | This control expands what remote agents can do on this machine. |
| [Registration of older clients](../../src/metaform/modules/node/__init__.py#L104) (`node_dcr`) | **Replace:** Metaform should preserve account approval when changing how clients register. | The gate should protect client registration, rather than worker identity. |
| [Hosted service hostname](../../src/metaform/modules/node/__init__.py#L39) (`node_domain`) | **Replace:** Metaform should match the hostname to the assigned deployment. | The hostname controls where clients connect. |
| [Remote deployment machine](../../src/metaform/modules/node/__init__.py#L108) (`node_host`) | **Replace:** Metaform should match the remote machine to the assigned deployment. | The host determines which remote machine receives commands. |
| [Other accounts' permission to launch workers](../../src/metaform/modules/node/__init__.py#L99) (`node_member_dispatch`) | **Replace:** Metaform should require account approval before expanding another account's execution access. | This control changes account access, rather than ordinary worker duties. |
| [Hosted service connection method](../../src/metaform/modules/node/__init__.py#L44) (`node_mode`) | **Replace:** Metaform should retain encrypted connections when changing the hosting mode. | The connection method must not remove connection protection. |
| [Project folders available remotely](../../src/metaform/modules/node/__init__.py#L70) (`node_projects`) | **Replace:** Metaform should reject added folders outside the assigned project scope. | This control exposes files to remote operations. |
| [Persistence of reused-token detection](../../src/metaform/modules/node/__init__.py#L88) (`node_refresh_replay`) | **Replace:** Metaform should require your actual instruction before reducing protection across server restarts. | Durable storage keeps reused-token detection effective after server restarts. |
| [Access through a relay connection](../../src/metaform/modules/node/__init__.py#L62) (`node_relay_capability`) | **Replace:** Metaform should require your actual instruction before expanding remote access. | This control expands what remote agents can do on this machine. |
| [Hosted service or connection broker](../../src/metaform/modules/node/__init__.py#L80) (`node_role`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The server's assigned purpose determines its function, rather than the worker label. |
| [Deployment login key file](../../src/metaform/modules/node/__init__.py#L111) (`node_ssh_identity`) | **Replace:** Metaform should accept only a login key available to the assigned deployment. | An existing deployment key does not require a specially named worker. |
| [Key installed on a new remote machine](../../src/metaform/modules/node/__init__.py#L125) (`node_ssh_public_key`) | **Replace:** Metaform should verify that the login key belongs to the assigned deployment. | This key changes who can log into the remote machine. |

#### Outside work through Paperclip

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Extra permission for sending work through agent tools](../../src/metaform/modules/paperclip/__init__.py#L128) (`paperclip_agents_may_send`) | **Retire:** Metaform should retire this extra sending ban and use the same action checks for the agent tools and terminal. | The terminal already permits the same send without this extra worker restriction. |
| [Default outside worker](../../src/metaform/modules/paperclip/__init__.py#L112) (`paperclip_assignee`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Choosing a recipient does not grant control over that worker. |
| [Interval between outside-work checks](../../src/metaform/modules/paperclip/__init__.py#L118) (`paperclip_check_minutes`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A worker label does not validate the interval between checks. |
| [Outside company account](../../src/metaform/modules/paperclip/__init__.py#L110) (`paperclip_company`) | **Replace:** Metaform should verify that the configured account permits access to the selected company. | The company determines which account's records Metaform reads or changes. |
| [Outside project](../../src/metaform/modules/paperclip/__init__.py#L115) (`paperclip_project`) | **Replace:** Metaform should match the destination project to the assigned work. | The project determines where Metaform creates work. |
| [Outside-work credential name](../../src/metaform/modules/paperclip/__init__.py#L105) (`paperclip_token_env`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | An existing credential reference does not require a specially named worker. |
| [Outside-work service address](../../src/metaform/modules/paperclip/__init__.py#L101) (`paperclip_url`) | **Replace:** Metaform should accept only the service address covered by the assigned connection task. | The service address determines where Metaform sends work. |

#### Phone service

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Phone-service listening address](../../src/metaform/modules/twilio/__init__.py#L143) (`twilio_bind`) | **Replace:** Metaform should require an explicit task request before exposing the service beyond this computer. | The gate should protect network exposure, rather than worker labels. |
| [Minimum interval between automatic calls](../../src/metaform/modules/twilio/__init__.py#L180) (`twilio_call_gap_minutes`) | **Replace:** Metaform should require your actual instruction before shortening your stated call interval. | Workers must not defeat your limit on repeated calls. |
| [Events that trigger calls](../../src/metaform/modules/twilio/__init__.py#L168) (`twilio_call_when`) | **Replace:** Metaform should allow only notification events covered by the current task. | The chosen events can trigger contact without another instruction. |
| [Verification of incoming callers](../../src/metaform/modules/twilio/__init__.py#L157) (`twilio_caller_proof`) | **Replace:** Metaform should require your actual instruction before weakening incoming-caller verification. | This control determines whether an incoming caller counts as you. |
| [Phone-service certificate file](../../src/metaform/modules/twilio/__init__.py#L150) (`twilio_certificate`) | **Replace:** Metaform should verify that the certificate matches the assigned phone-service address. | Correct certificates protect incoming phone-service events. |
| [Phone-service activation](../../src/metaform/modules/twilio/__init__.py#L117) (`twilio_enabled`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Enabling assigned communication does not authorize arbitrary recipients. |
| [Phone transcription service](../../src/metaform/modules/twilio/__init__.py#L192) (`twilio_hearing`) | **Replace:** Metaform should match the service to the assigned speech task. | Recorded speech must reach the intended transcription service. |
| [Phone-service number](../../src/metaform/modules/twilio/__init__.py#L125) (`twilio_number`) | **Replace:** Metaform should verify that the configured account controls the chosen phone number. | The account must actually control the selected number. |
| [Trusted callers and permitted recipients](../../src/metaform/modules/twilio/__init__.py#L128) (`twilio_owner_numbers`) | **Replace:** Metaform should require your actual instruction before changing trusted caller and recipient numbers. | These numbers can let callers reach your user agent as you. |
| [Project that answers phone calls](../../src/metaform/modules/twilio/__init__.py#L202) (`twilio_project`) | **Replace:** Metaform should match the phone conversation to the requested project. | Otherwise the caller could direct work in the wrong project. |
| [Address receiving phone-service events](../../src/metaform/modules/twilio/__init__.py#L134) (`twilio_public_url`) | **Replace:** Metaform should match the address to the assigned phone service. | The address determines where the provider sends call and text events. |
| [Events that trigger texts](../../src/metaform/modules/twilio/__init__.py#L176) (`twilio_text_when`) | **Replace:** Metaform should allow only notification events covered by the current task. | The chosen events can trigger contact without another instruction. |

#### Project board selection

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Default project board](../../src/metaform/modules/map/__init__.py#L126) (`board`) | **Replace:** Metaform should allow board selection without releasing deliberately held tickets. | Selecting a board must not silently release held tickets. |

#### Worker programs and models

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Default worker program](../../src/metaform/modules/dispatch/__init__.py#L315) (`dispatch_agent`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A supported program matters more than the selecting worker's label. |
| [Antigravity launch command](../../src/metaform/modules/dispatch/__init__.py#L579) (`dispatch_antigravity`) | **Replace:** Metaform should accept only the program source and version covered by the assigned task. | The program source determines what code Metaform will run. |
| [Antigravity thinking effort](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_antigravity_effort`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Antigravity fast mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_antigravity_fast`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Antigravity operating mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_antigravity_mode`) | **Replace:** Metaform should require your actual instruction before expanding permissions beyond the current task. | Workers must not expand permissions beyond the assigned work. |
| [Antigravity model](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_antigravity_model`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Antigravity selection guidance](../../src/metaform/modules/dispatch/__init__.py#L487) (`dispatch_antigravity_strengths`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Selection guidance describes abilities without granting privileges. |
| [Claude launch command](../../src/metaform/modules/dispatch/__init__.py#L579) (`dispatch_claude`) | **Replace:** Metaform should accept only the program source and version covered by the assigned task. | The program source determines what code Metaform will run. |
| [Claude agent option](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_claude_agent`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Claude thinking effort](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_claude_effort`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Claude fast mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_claude_fast`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Claude operating mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_claude_mode`) | **Replace:** Metaform should require your actual instruction before expanding permissions beyond the current task. | Workers must not expand permissions beyond the assigned work. |
| [Claude model](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_claude_model`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Claude selection guidance](../../src/metaform/modules/dispatch/__init__.py#L487) (`dispatch_claude_strengths`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Selection guidance describes abilities without granting privileges. |
| [Codex launch command](../../src/metaform/modules/dispatch/__init__.py#L579) (`dispatch_codex`) | **Replace:** Metaform should accept only the program source and version covered by the assigned task. | The program source determines what code Metaform will run. |
| [Codex collaboration mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_codex_collaboration_mode`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A collaboration mode does not grant control over another worker. |
| [Codex thinking effort](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_codex_effort`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Codex fast mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_codex_fast`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Codex operating mode](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_codex_mode`) | **Replace:** Metaform should require your actual instruction before expanding permissions beyond the current task. | Workers must not expand permissions beyond the assigned work. |
| [Codex model](../../src/metaform/modules/dispatch/__init__.py#L818) (`dispatch_codex_model`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The program's supported choices validate this setting, rather than worker identity. |
| [Codex selection guidance](../../src/metaform/modules/dispatch/__init__.py#L487) (`dispatch_codex_strengths`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Selection guidance describes abilities without granting privileges. |
| [Available additional worker programs](../../src/metaform/modules/dispatch/__init__.py#L261) (`dispatch_registry_agents`) | **Replace:** Metaform should accept only the program source and version covered by the assigned task. | Program names and versions determine which software Metaform runs. |
| [List of available worker programs](../../src/metaform/modules/dispatch/__init__.py#L269) (`dispatch_registry_url`) | **Replace:** Metaform should accept only the program source and version covered by the assigned task. | The list's source determines which software Metaform trusts. |
| [Program connected to the editor](../../src/metaform/modules/dispatch/serve.py#L64) (`dispatch_serve_agent`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | A supported program matters more than the selecting worker's label. |
| [Program used for your user agent](../../src/metaform/modules/dispatch/__init__.py#L842) (`dispatch_system_agent`) | **Replace:** Metaform should allow program selection without transferring the user agent's shutdown rights. | Changing its program must not grant another worker your user agent's shutdown rights. |

#### Speech and microphone

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Transcription credential name](../../src/metaform/modules/voice/__init__.py#L127) (`voice_endpoint_key_env`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | An existing credential reference does not require a specially named worker. |
| [Transcription model](../../src/metaform/modules/voice/__init__.py#L124) (`voice_endpoint_model`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The service's supported choices validate this setting, rather than worker identity. |
| [Transcription service address](../../src/metaform/modules/voice/__init__.py#L119) (`voice_endpoint_url`) | **Replace:** Metaform should match the service to the assigned speech task. | The service address determines who receives recorded speech. |
| [Speech transcription engine](../../src/metaform/modules/voice/__init__.py#L77) (`voice_engine`) | **Replace:** Metaform should match the service to the assigned speech task. | The assigned speech task determines the appropriate service. |
| [Forwarding of recorded audio](../../src/metaform/modules/voice/__init__.py#L108) (`voice_send_audio`) | **Replace:** Metaform should forward audio only to the recipient covered by the speech task. | Forwarding audio can expose information that text alone does not contain. |
| [Spoken-reply service](../../src/metaform/modules/voice/__init__.py#L144) (`voice_tts`) | **Replace:** Metaform should match the service to the assigned speech task. | The assigned speech task determines the appropriate service. |
| [Continuous microphone listening](../../src/metaform/modules/voice/__init__.py#L158) (`voice_wake`) | **Replace:** Metaform should require your actual instruction before enabling continuous microphone listening. | Continuous listening changes what the microphone records without another action. |

#### Web-page address

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Web-page listening address](../../src/metaform/modules/web/__init__.py#L61) (`web_bind`) | **Replace:** Metaform should require an explicit task request before exposing the service beyond this computer. | The gate should protect network exposure, rather than worker labels. |

#### Recovery and progress warnings

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Recovery of failed workers](../../src/metaform/modules/dispatch/__init__.py#L328) (`dispatch_recovery`) | **Replace:** Metaform should permit recovery changes without restarting work covered by an explicit stop. | Recovery must respect an explicit stop regardless of the worker label. |
| [Repeated-failure warning threshold](../../src/metaform/modules/dispatch/__init__.py#L363) (`dispatch_repeat_failures`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Actual failures determine the warning, rather than worker identity. |
| [Automatic retry count](../../src/metaform/modules/dispatch/__init__.py#L424) (`dispatch_retries`) | **Replace:** Metaform should permit recovery changes without restarting work covered by an explicit stop. | A retry count must not override an explicit stop. |
| [Limit on unsuccessful attempts](../../src/metaform/modules/dispatch/__init__.py#L365) (`dispatch_rework_limit`) | **Replace:** Metaform should require the pause-release instruction before resuming deliberately paused work. | Workers must not bypass an intentional pause by changing its trigger. |
| [Silence warning threshold](../../src/metaform/modules/dispatch/__init__.py#L419) (`dispatch_silence_seconds`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Actual silence determines the warning, rather than worker identity. |
| [No-progress tool-call threshold](../../src/metaform/modules/dispatch/__init__.py#L359) (`dispatch_spin_calls`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Recorded progress determines the warning, rather than worker identity. |
| [No-progress time threshold](../../src/metaform/modules/dispatch/__init__.py#L361) (`dispatch_spin_minutes`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | Recorded progress determines the warning, rather than worker identity. |

#### Code changes, verification and notes

| Control | Gate recommendation | Why |
| --- | --- | --- |
| [Retention of closed, unmerged branches](../../src/metaform/modules/dispatch/__init__.py#L375) (`dispatch_abandoned_branch_days`) | **Replace:** Metaform should allow assigned retention changes and preserve recoverable unmerged commits before deleting a branch. | Deleting a branch must not make its unmerged changes unrecoverable. |
| [Notes after a failure](../../src/metaform/modules/dispatch/__init__.py#L414) (`dispatch_record_on_failure`) | **Remove:** Metaform should remove the worker ban on this setting. | The worker ban prevents disabling an unrequested extra duty. |
| [Notes after ticket completion](../../src/metaform/modules/dispatch/__init__.py#L392) (`dispatch_record_on_finish`) | **Remove:** Metaform should remove the worker ban on this setting. | The worker ban prevents disabling an unrequested extra duty. |
| [Notes after a stop](../../src/metaform/modules/dispatch/__init__.py#L406) (`dispatch_record_on_stop`) | **Replace:** Metaform should never restart a stopped worker merely to record notes. | Your stop must remain effective despite the recording setting. |
| [Project verification command](../../src/metaform/modules/dispatch/__init__.py#L382) (`dispatch_test_command`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | The test command must match the project, rather than the worker label. |
| [Separate work directories](../../src/metaform/modules/dispatch/__init__.py#L372) (`dispatch_worktrees`) | **Remove:** Metaform should remove the worker ban. Metaform should keep existing value checks. | File-conflict checks must protect work regardless of directory layout. |

#### Strengths settings for additional installed agents

Metaform creates additional strengths settings when you install other agent programs.

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Each additional agent's selection guidance (`dispatch_<agent>_strengths`) | **Remove:** Metaform should remove the same worker ban for every installed agent. | Selection guidance describes abilities without granting privileges. |

## [ ] 2. Metaform hides some settings from workers

- **Now:** Metaform omits some settings from the agent tools.
- **Recommendation:** Metaform should remove worker-based hiding of setting names and allowed values. Metaform should apply entry 1 before changing a setting.
- **Why:** Hiding a setting does not validate a change to that setting.
- **After removal:** Workers could discover these settings through the agent tools.
- **Pros:** Workers could find available controls without asking another agent.
- **Cons:** Workers could receive more settings information than their task needs.
- **Source:** [Settings visibility](../../src/metaform/modules/mcp/server.py#L165).

## [ ] 3. Metaform reserves some commands for your direct use

- **Now:** Metaform rejects workers on commands that require your direct use.
- **Recommendation:** Metaform should replace the general worker ban with the command rules below.
- **Why:** One worker ban cannot distinguish ordinary work from destructive changes.
- **After removal:** Workers could request these commands without switching to your page or terminal.
- **Pros:** Workers could complete ordinary work while retaining their existing understanding.
- **Cons:** Workers could request destructive actions unless Metaform keeps separate protections.
- **Source:** [Command restrictions](../../src/metaform/modules/mcp/server.py#L710).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Clear project records (`clear_project`) | **Replace:** Metaform should accept your specific instruction through any worker and retain project, backup and overwrite checks. | These operations can replace project records, so the exact intended change must remain explicit. |
| Restore project records (`restore_project`) | **Replace:** Metaform should accept your specific instruction through any worker and retain project, backup and overwrite checks. | These operations can replace project records, so the exact intended change must remain explicit. |
| Save agent instructions (`save_prompt`) | **Replace:** Metaform should accept assigned prompt edits from any worker and retain prompt names, versions and edit history. | Prompt edits affect future agent instructions, so changes must retain their exact target and source. |
| Create a new active map (`map add-base`) | **Replace:** Metaform should accept the actual new-map instruction through any worker and retain map-name validation and switching warnings. | A new active map changes the project view and where subsequent work appears. |
| Switch the active map (`map activate`) | **Replace:** Metaform should accept the actual switch instruction through any worker and retain named-map and running-work checks. | Existing workers remain attached to their original map when the displayed map changes. |
| Remove a saved map (`map remove-base`) | **Replace:** Metaform should accept the actual removal instruction through any worker and retain backups and active-map refusal. | The worker label adds no protection beyond confirming the intended map and preserving recoverability. |
| Rewrite a map while keeping the original (`map collapse`) | **Replace:** Metaform should accept the actual rewrite instruction through any worker and preserve the original map and object identifiers. | Rewriting a map must not discard its original evidence or detach existing records. |
| Discard an unfinished intake (`intake discard`) | **Replace:** Metaform should accept your actual discard instruction through any worker and retain unfinished-intake and backup checks. | Discarding removes recorded intake work, so the request must identify that work. |
| Start intake using a new map (`intake start with a new map name`) | **Replace:** Metaform should accept your actual new-map choice through any worker and keep ordinary updates on the existing map. | Starting another map can separate knowledge and leave address-based memories unmatched. |
| Create a separate project map (`dispatch intake map=new`) | **Replace:** Metaform should accept your actual new-map choice through any worker and retain map=extend as the ordinary update route. | This command creates a map beside the existing map, rather than replacing it. |
| Launch work from a held ticket (`dispatch start on held tickets`) | **Replace:** Metaform should accept an instruction authorizing the named hold release and record who supplied it. | A deliberate hold must remain effective until the relevant instruction changes. |
| Run work from a held ticket (`dispatch run on held tickets`) | **Replace:** Metaform should accept an instruction authorizing the named hold release and record who supplied it. | A deliberate hold must remain effective until the relevant instruction changes. |
| Record a roundtable decision (`roundtables decide`) | **Replace:** Metaform should accept your actual decision through any worker and retain reviewed contents, saved version and final execution approval. | Correct forwarding must not allow a worker to invent execution approval. |
| Create work from a roundtable idea (`roundtables adopt`) | **Replace:** Metaform should allow assigned adoption of the named idea and retain ended-table, idea and destination checks. | Creating an authorized ticket needs no privileged worker identity. |
| Restore an example project backup (`hello base-restore`) | **Replace:** Metaform should accept your actual restore instruction through any worker and retain the selected backup and project checks. | The example restore path must provide the same record protections as ordinary restoration. |

## [ ] 4. Metaform requires a separate path for clearing or restoring project history

- **Now:** Metaform blocks these history operations through the agent tools.
- **Recommendation:** Metaform should accept your actual clear-project or restore-project instruction through any worker. Metaform should retain the exact project, selected backup and existing backup protections.
- **Why:** The intended project and backup protect the records, rather than the worker's label.
- **After removal:** Workers could request these history operations through the agent tools.
- **Pros:** Workers could follow your specific instruction without a separate page visit.
- **Cons:** A worker could remove or replace the wrong project history.
- **Source:** [History operations](../../src/metaform/modules/mcp/server.py#L629).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Clear project records (`clear_project`) | **Replace:** Metaform should accept your exact project instruction and preserve the named backup and overwrite checks. | The target and intended data change protect the records, rather than the worker label. |
| Restore project records (`restore_project`) | **Replace:** Metaform should accept your exact project instruction and preserve the named backup and overwrite checks. | The target and intended data change protect the records, rather than the worker label. |

## [ ] 5. Metaform recognizes your instructions differently across agents

- **Now:** Metaform recognizes some instructions only through particular agents and conversation records.
- **Recommendation:** Metaform should recognize your original instruction regardless of which worker carries it. Metaform should record the original message and the forwarding worker separately.
- **Why:** Workers can forward your instruction without becoming its author.
- **After removal:** Metaform would no longer reject an instruction solely because another worker carried it.
- **Pros:** You could direct an informed worker without repeating your instruction elsewhere.
- **Cons:** Workers could misrepresent their own decisions unless Metaform preserves the real source.
- **Source:** [Instruction recognition](../../src/metaform/module.py#L1004).

## [ ] 6. Metaform hides extra tool instructions from some workers

- **Now:** Metaform gives ordinary instructions to workers. Metaform limits some extra instructions to particular agent types.
- **Recommendation:** Metaform should remove the worker-type test when selecting extra tool instructions. Metaform should show the extra work and intake guidance when those operations apply.
- **Why:** Workers need the same applicable instructions to use the same tools correctly.
- **After removal:** Workers could read the extra instructions through the agent tools.
- **Pros:** Workers could understand useful controls without asking a specially named agent.
- **Cons:** Metaform could show workers page instructions that do not apply to their tools.
- **Source:** [Extra instruction selection](../../src/metaform/modules/mcp/server.py#L1030).

## [ ] 7. Metaform can hide or disable tools for individual workers

- **Now:** Metaform can withhold whole tool groups or selected read commands from a worker.
- **Recommendation:** Metaform should remove tool restrictions imposed solely because of worker type. Metaform should retain limits that enforce the current investigation-only or otherwise restricted assignment.
- **Why:** The current assignment determines allowed work, rather than a permanent worker label.
- **After removal:** Workers could discover and request the affected tools.
- **Pros:** Workers could perform related tasks without starting replacement workers.
- **Cons:** Workers could exceed an investigation-only assignment if Metaform also removed its deliberate tool limits.
- **Source:** [Tool withholding](../../src/metaform/module.py#L780).

## [ ] 8. Metaform redirects some worker questions to its page

- **Now:** Metaform disables the application's question form for some workers. Metaform can route their questions to the same conversation's page.
- **Recommendation:** Metaform should allow dispatched workers to use question forms their application supports. Metaform should use page forms when that application cannot show forms.
- **Why:** The application's form support determines whether it can show a question.
- **After removal:** These workers could use their application's question form when the application supports it.
- **Pros:** You could answer without opening a different page.
- **Cons:** Metaform would need to prevent duplicate questions across the available forms.
- **Source:** [Question form selection](../../src/metaform/modules/mcp/consent.py#L51).

## [ ] 9. Metaform can require another confirmation

- **Now:** Metaform can pause an action until you complete a confirmation form.
- **Recommendation:** Metaform should reuse a recorded decision only when the action, target, scope and reviewed contents remain unchanged. Metaform should ask again when those details change or required information remains missing.
- **Why:** A repeated confirmation adds no protection when the action and its target remain unchanged.
- **After removal:** Metaform could perform the affected actions without this confirmation.
- **Pros:** You would avoid repeated confirmations for work you already directed.
- **Cons:** Metaform could perform an action before you resolve an unclear request.
- **Source:** [Confirmation checks](../../src/metaform/modules/mcp/server.py#L2708).

## [ ] 10. Metaform blocks workers from changing outside-agent connections

- **Now:** Metaform rejects worker requests to add or remove outside-agent connections through the agent tools.
- **Recommendation:** Metaform should allow assigned additions and removals of named outside-agent connections. Metaform should retain address validation, secret handling and destination records.
- **Why:** The intended service and its address matter more than the worker's label.
- **After removal:** Workers could add or remove these connections through the agent tools.
- **Pros:** Workers could repair a required connection without moving the task elsewhere.
- **Cons:** Workers could connect the project to an unintended outside service.
- **Source:** [Connection changes](../../src/metaform/modules/mcp/a2a_peers.py#L122).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Add an outside-agent connection | **Replace:** Metaform should allow the assigned connection after validating its address and configured access. | A verified destination protects work without requiring a special worker. |
| Remove an outside-agent connection | **Replace:** Metaform should allow removal of the connection named by the task. | The exact connection matters more than the worker requesting removal. |

## [ ] 11. Metaform no longer gives launch requesters control over workers

- **Now:** Earlier changes removed the rule that gave launch requesters special shutdown rights.
- **Recommendation:** Metaform should keep launch-requester shutdown rights removed. Metaform should restrict directed worker shutdown to you and the user agent.
- **Why:** Requesting a launch must not grant control over the launched worker.
- **After removal:** The removal stopped treating a launch requester as another worker's controller.
- **Pros:** Workers no longer gain control by requesting another worker.
- **Cons:** Metaform would lose no required protection after Metaform adds the correct shutdown restriction.
- **Source:** [Current worker shutdown](../../src/metaform/modules/dispatch/__init__.py#L4688).

## [ ] 12. Metaform currently lets workers request a project-wide shutdown

- **Now:** Metaform no longer limits shutdown by launch requester. The current command lacks your required shutdown restriction.
- **Recommendation:** Metaform should reject ordinary worker calls to stop and stop-all. Metaform should keep system cleanup and shutdown directed by you or the user agent.
- **Why:** Your shutdown rule reserves these decisions for you and the user agent.
- **After removal:** The earlier removal lets a worker stop other workers regardless of who requested their launch.
- **Pros:** Workers could stop stalled work without waiting for you.
- **Cons:** A worker could stop every other worker against your stated rule. You could lose their useful understanding.
- **Source:** [Project-wide worker shutdown](../../src/metaform/modules/dispatch/__init__.py#L4756).

## [ ] 13. Metaform groups permission and program controls under one worker restriction

- **Now:** Metaform groups launch permissions, available-program changes and permission-response settings under one worker restriction.
- **Recommendation:** Metaform should replace the shared worker ban with the nine control rules below.
- **Why:** The actual permission change matters more than the worker's identity.
- **After removal:** Workers could request all controls covered by this restriction.
- **Pros:** Workers could adjust ordinary ticket settings without changing workers.
- **Cons:** Workers could broaden permissions or change executable programs without the listed replacement checks.
- **Source:** [Ticket control check](../../src/metaform/modules/dispatch/__init__.py#L6043).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Choose launch tool permissions (`dispatch start prompts=<policy>`) | **Replace:** Metaform should allow assigned permission settings and retain supported values and your stated permission limits. | Workers need configuration access, but must not silently override permission limits you established. |
| Choose the worker operating mode (`dispatch start mode=<mode>`) | **Replace:** Metaform should allow assigned permission settings and retain supported values and your stated permission limits. | Workers need configuration access, but must not silently override permission limits you established. |
| Add an available worker program (`dispatch registry add=<agent>`) | **Replace:** Metaform should allow assigned registry changes and retain valid agent identifiers, package sources and fixed program versions. | These changes select programs that run, so software identity and requested versions must remain explicit. |
| Remove an available worker program (`dispatch registry remove=<agent>`) | **Replace:** Metaform should allow assigned registry changes and retain valid agent identifiers, package sources and fixed program versions. | These changes select programs that run, so software identity and requested versions must remain explicit. |
| Upgrade available worker programs (`dispatch registry upgrade=true`) | **Replace:** Metaform should allow assigned registry changes and retain valid agent identifiers, package sources and fixed program versions. | These changes select programs that run, so software identity and requested versions must remain explicit. |
| Change worker tool permissions (`dispatch prompts <work> <policy>`) | **Replace:** Metaform should allow assigned policy changes and retain supported choices and explicit authorization for approve-all. | Changing a permission policy is different from inventing your answer to a pending permission question. |
| Change worker-program options (`dispatch configure`) | **Keep available:** Metaform should leave supported worker-program settings available and retain the values offered by the worker program. | The current shared worker check does not guard these commands. |
| Adjust worker model options (`dispatch tune`) | **Keep available:** Metaform should leave supported worker-program settings available and retain the values offered by the worker program. | The current shared worker check does not guard these commands. |
| Cancel work that can end a worker (`dispatch cancel`) | **Apply shutdown rule:** Metaform should restrict cancellation that ends a worker to you or the user agent. | The current command can end a session, so the shutdown rule still applies. |

## [ ] 14. Metaform rejects agent answers to permission questions

- **Now:** Metaform rejects permission answers from workers and the user agent.
- **Recommendation:** Metaform should accept an answer you supplied from any worker carrying that answer. Metaform should match it to the waiting question and record your original message.
- **Why:** Your original answer establishes the decision, regardless of which worker forwards it.
- **After removal:** Workers could submit permission answers through these tools.
- **Pros:** Workers could deliver an answer you already supplied without changing workers.
- **Cons:** Workers could present their own answers as yours without a separate source check.
- **Source:** [Permission answers](../../src/metaform/modules/dispatch/__init__.py#L6054).

## [ ] 15. Metaform treats worker launch requests differently

- **Now:** Metaform can apply automatic-start rules differently to workers and the user agent.
- **Recommendation:** Metaform should accept launch requests from every worker. Metaform should apply slot limits, configured budgets and existing stop records to every launch.
- **Why:** Capacity, spending and stop checks determine whether Metaform can launch another worker.
- **After removal:** Metaform would assess these launch requests without this worker distinction.
- **Pros:** Workers could obtain needed help without transferring the whole task.
- **Cons:** Workers could create unnecessary work unless Metaform keeps shared limits.
- **Source:** [Launch requests](../../src/metaform/modules/dispatch/__init__.py#L2860).

## [ ] 16. Metaform limits who can relay your instructions

- **Now:** Metaform normally treats worker messages as worker messages. Metaform recognizes forwarded user instructions only through certain agent conversations.
- **Recommendation:** Metaform should attach your original message to forwarded decisions from any worker. Metaform should label workers' own messages as worker messages.
- **Why:** Forwarding must preserve who actually supplied the instruction.
- **After removal:** Metaform could treat messages from more workers as your instructions.
- **Pros:** You could direct an informed worker without moving the conversation.
- **Cons:** Workers could mislabel their own decisions as your instructions.
- **Source:** [Instruction relay](../../src/metaform/modules/dispatch/peering.py#L363).

## [ ] 17. Metaform protects intentional holds and separate-map choices

- **Now:** Metaform can require a recognized instruction before releasing held work or creating a separate map.
- **Recommendation:** Metaform should retain explicit release of deliberately held tickets and the choice between new and extended maps. Metaform should accept your actual instruction through any worker.
- **Why:** Intentional holds and a separate-map choice carry different consequences from ordinary ticket coordination.
- **After removal:** Workers could release held work or create a separate map without this instruction check.
- **Pros:** Workers could avoid repeated instruction checks when you already supplied a valid decision.
- **Cons:** Workers could restart deliberately held work. A separate map could split the project's knowledge.
- **Source:** [Held work](../../src/metaform/modules/dispatch/__init__.py#L1752).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Launch work from a deliberately held ticket (`dispatch start on a deliberately held ticket`) | **Replace:** Metaform should accept an instruction authorizing the named hold release from any worker carrying that instruction. | The replacement gate preserves intentional holds without forcing a different worker conversation. |
| Run work from a deliberately held ticket (`dispatch run on a deliberately held ticket`) | **Replace:** Metaform should accept an instruction authorizing the named hold release from any worker carrying that instruction. | The replacement gate preserves intentional holds without forcing a different worker conversation. |
| Create a separate project map (`dispatch intake map=new`) | **Replace:** Metaform should accept your actual new-map choice and otherwise use map=extend for an existing project map. | A separate map can fragment knowledge even though the original map remains intact. |

## [ ] 18. Metaform limits how agents submit roundtable decisions

- **Now:** Metaform requires a recognized user decision before accepting certain roundtable decisions.
- **Recommendation:** Metaform should accept your actual roundtable decision when any worker forwards it. Metaform should retain checks on the reviewed output's exact contents, saved version and final execution approval.
- **Why:** Your approval must cover the exact reviewed output before execution starts.
- **After removal:** Workers could submit decisions without this user-source check.
- **Pros:** Workers could deliver your decision without another page interaction.
- **Cons:** A worker could approve execution without your actual approval.
- **Source:** [Roundtable decisions](../../src/metaform/modules/roundtables/pipeline.py#L417).

## [ ] 19. Metaform checks who can replace a roundtable answer

- **Now:** Metaform accepts an answer from the original connection or a participant's secret key.
- **Recommendation:** Metaform should keep the original-connection or seat-key check when recording participant answers. Metaform should retain earlier answers when recording requested corrections.
- **Why:** One participant must not silently replace another participant's answer.
- **After removal:** Another participant could submit an answer under the original participant's identity.
- **Pros:** Participants could submit corrections without recovering the original connection or key.
- **Cons:** Participants could silently replace another participant's answer.
- **Source:** [Roundtable answer author check](../../src/metaform/modules/roundtables/roundtable/server.py#L433).

## [ ] 20. Metaform checks for the service that prepares roundtable results

- **Now:** The earlier repair connected automatic preparation to the current task service. Metaform checks that this service exists.
- **Recommendation:** Metaform should keep automatic research, architecture, intake, planning and ticket preparation through the current task service. Metaform should retain required-service checks and the final execution-approval stop.
- **Why:** Automatic preparation needs the task service, rather than a coordinator worker.
- **After removal:** Metaform would attempt preparation without first checking for its required task service.
- **Pros:** Workers gain no useful capability from removing this check.
- **Cons:** Metaform could fail without explaining how to enable the missing service.
- **Source:** [Required task service](../../src/metaform/modules/roundtables/pipeline.py#L138).

## [ ] 21. Metaform can reject a worker based on its agent name

- **Now:** Metaform can compare a worker's agent name with the ticket's allowed names.
- **Recommendation:** Metaform should remove ticket rejection based only on a program name such as codex or claude. Metaform should retain your explicit model choices and actual tool requirements.
- **Why:** A worker's supported tools determine suitability more accurately than its name.
- **After removal:** Workers could attempt tickets that currently exclude their agent name.
- **Pros:** An informed worker could continue instead of transferring its task.
- **Cons:** A worker could attempt work that needs tools or abilities it lacks.
- **Source:** [Agent-name check](../../src/metaform/modules/dispatch/__init__.py#L1652).

## [ ] 22. Metaform can drop media from worker messages

- **Now:** Metaform routes worker messages through a text-only path. That path can omit supplied images or audio.
- **Recommendation:** Metaform should forward supported images and audio alongside worker messages instead of discarding them. Metaform should retain the sender, attachment source and intended recipient.
- **Why:** Workers lose useful evidence when Metaform silently discards attachments.
- **After removal:** Workers could forward supported images or audio with their messages.
- **Pros:** Workers could retain evidence that text alone cannot convey.
- **Cons:** Workers could forward material to the wrong recipient without destination checks.
- **Source:** [Worker messages](../../src/metaform/modules/dispatch/__init__.py#L4182).

## [ ] 23. Metaform can suppress worker questions

- **Now:** Metaform can suppress a worker's question and return a preset response. This path can also affect the current user agent.
- **Recommendation:** Metaform should deliver every worker's question through the existing chat or supported question form. Metaform should never fill answer fields with its own preset response.
- **Why:** A preset response cannot substitute for the answer a worker needs from you.
- **After removal:** Workers could present questions that this restriction currently suppresses.
- **Pros:** Workers could obtain missing information while keeping their existing understanding.
- **Cons:** Workers could interrupt you more often with unnecessary questions.
- **Source:** [Worker questions](../../src/metaform/modules/dispatch/runner.py#L3013).

## [ ] 24. Metaform counts some agent types under different slot limits

- **Now:** Metaform can apply different slot limits to workers, helpers and the user agent.
- **Recommendation:** Metaform should apply project and machine slot limits to every project worker. Metaform should reserve capacity for the user agent.
- **Why:** Worker labels must not bypass resource limits or prevent your user agent from working.
- **After removal:** Metaform would stop applying these separate slot limits.
- **Pros:** Workers could obtain help despite a limit tied to their label.
- **Cons:** Workers could exhaust resources unless Metaform keeps a shared limit. Workers could also block the user agent from starting.
- **Source:** [Available slot checks](../../src/metaform/modules/dispatch/__init__.py#L3275).

## [ ] 25. Metaform blocks workers from submitting workflow answers

- **Now:** Metaform can reject an answer from a worker and direct you to the terminal.
- **Recommendation:** Metaform should accept your supplied answer through any worker using workflow answer. Metaform should retain the run identifier, waiting question and required answer format.
- **Why:** The supplied answer and waiting question establish a valid continuation.
- **After removal:** Workers could submit answers to the waiting workflow.
- **Pros:** You could answer in the existing conversation without repeating the answer elsewhere.
- **Cons:** A worker could substitute its own answer for a decision the workflow requires from you.
- **Source:** [Workflow answers](../../src/metaform/modules/workflow/__init__.py#L326).

## [ ] 26. Metaform blocks workers from changing memory locks

- **Now:** Metaform rejects worker requests to lock or unlock memory through these tools.
- **Recommendation:** Metaform should expose memory lock and unlock to every worker. Metaform should preserve deliberate locks until an instruction authorizes the relevant unlock.
- **Why:** An intentional lock protects information, but a worker label does not explain an unlock request.
- **After removal:** Workers could change memory locks through these tools.
- **Pros:** Workers could maintain memory protection without transferring the task.
- **Cons:** A worker could unlock protected memory and permit unwanted changes.
- **Source:** [Memory locks](../../src/metaform/modules/memory/__init__.py#L1357).

## [ ] 27. Metaform accepts map notes only through its page

- **Now:** Metaform rejects map-note changes through the agent tools and terminal.
- **Recommendation:** Metaform should allow assigned map-note edits through agent tools and the terminal. Metaform should retain the prior note and actual author when applying an edit.
- **Why:** The note's target, prior contents and actual author protect its meaning.
- **After removal:** Workers could write map notes without using the page.
- **Pros:** Workers could maintain assigned map notes through their existing tools.
- **Cons:** Workers could overwrite notes you intended to maintain yourself.
- **Source:** [Map notes](../../src/metaform/modules/memory/__init__.py#L1325).

## [ ] 28. Metaform blocks workers from selected web actions

- **Now:** Metaform uses one worker restriction across settings, instructions, board changes and agent controls.
- **Recommendation:** Metaform should replace the general web restriction with the 26 action rules below. Metaform should retain page authentication and request validation.
- **Why:** The requested action determines the required protection, rather than the worker's label.
- **After removal:** Workers could request the affected web actions.
- **Pros:** Workers could use useful actions that their other tools do not provide.
- **Cons:** Workers could also request destructive changes or worker shutdown.
- **Source:** [Web action checks](../../src/metaform/modules/web/server.py#L1251).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Answer a tool-permission question (`/api/dispatch-permit`) | **Replace:** Metaform should accept your actual answer from any worker and retain the waiting request identifier. | The replacement gate forwards your answer without allowing a worker to fabricate consent. |
| Save agent instructions (`/api/save-prompt`) | **Replace:** Metaform should allow assigned prompt edits and retain the prompt name, parent version and saved edit history. | The replacement gate permits useful prompt maintenance without silently replacing another saved version. |
| Clear project records (`/api/clear-project`) | **Replace:** Metaform should accept your actual clear instruction and retain the exact project, backup and running-work protections. | Clearing can remove project records and must target the project you actually named. |
| Unregister an empty project (`/api/remove-project`) | **Replace:** Metaform should allow the assigned removal and retain the empty-project check and original project files. | Removing an empty registration should not require a different worker or delete its folder. |
| Switch the active map (`/api/activate-base`) | **Replace:** Metaform should accept the requested map switch and retain the named-map and running-worker information. | Switching the page must not silently move workers away from their original maps. |
| Remove a saved map (`/api/remove-base`) | **Replace:** Metaform should accept the requested map removal and retain the backup and refusal to remove the active map. | These protections preserve records regardless of which worker forwards the instruction. |
| Restore project records (`/api/restore`) | **Replace:** Metaform should accept your actual restore instruction and retain the selected project, backup and current-state backup. | Restoration replaces records, so the exact source and target must remain explicit. |
| Clear board records (`/api/board-wipe`) | **Replace:** Metaform should accept your actual board-wipe instruction and retain the named board and permanent backup. | The named board and a recovery copy protect this deletion without a worker ban. |
| Restore board records (`/api/board-restore`) | **Replace:** Metaform should accept your actual restoration instruction and retain the named board, backup and existing-record checks. | Restoration must recover the selected records without overwriting unrelated subsequent work. |
| Register a project (`/api/add-project`) | **Remove:** Metaform should allow assigned project registration and retain identifier, folder and existing-registration checks. | Registering a valid project needs no specially named worker. |
| Discard an unfinished intake (`/api/intake-discard`) | **Replace:** Metaform should accept your actual discard instruction and retain checks identifying the unfinished intake and its saved copy. | Discarding the wrong intake would destroy useful recorded work. |
| Edit project memory (`/api/memory`) | **Remove:** Metaform should allow assigned memory edits and retain the correct map part, existing locks and actual author records. | Worker equality must not silently disable deliberate memory protection. |
| Change settings (`/api/settings`) | **Replace:** Metaform should apply entry 1 decisions to each named setting and retain value and project checks. | Different settings control ordinary work, spending and external services, so one blanket ban hides important differences. |
| Reset settings (`/api/settings/reset`) | **Replace:** Metaform should apply entry 1 decisions to every reset key and retain the exact project and reset scope. | A broad reset must not silently restore forbidden capabilities or erase unrelated configuration. |
| Change project tool permissions (`/api/dispatch-prompts`) | **Replace:** Metaform should allow assigned project permission-policy changes and retain supported choices and explicit authorization for approve-all. | A general setting change must not silently grant unrestricted tool execution. |
| Choose the default worker program (`/api/dispatch-agents`) | **Remove:** Metaform should allow assigned default-agent changes and retain configured-agent and valid-value checks. | Choosing a valid default worker program needs no privileged project worker. |
| Enable or disable project features (`/api/modules`) | **Replace:** Metaform should allow assigned module changes and preserve services still required by active work. | Workers need available tools without accidentally disabling services supporting current tasks. |
| Change worker tool permissions (`/api/dispatch-session-prompts`) | **Replace:** Metaform should allow assigned session policy changes and retain the session target and explicit authorization for approve-all. | The policy must change only the intended session and honor existing permission decisions. |
| Request a worker launch (`/api/dispatch-start`) | **Remove:** Metaform should accept every worker launch request and retain capacity, budget and stop checks. | Requesting a launch needs no special worker identity and grants no control over the launched worker. |
| Change worker-program options (`/api/dispatch-configure`) | **Remove:** Metaform should allow assigned worker-program configuration and retain session targeting and values supported by the worker program. | These existing value checks protect valid configuration without forcing another worker. |
| Cancel work that can end a worker (`/api/dispatch-cancel`) | **Replace:** Metaform should restrict cancellation that ends a worker to you or the user agent. | A worker must not gain authority to end another worker through a ticket-control route. |
| Assign a task (`/api/task-assign`) | **Remove:** Metaform should accept assigned task requests from any worker and retain task inputs, project targets and launch limits. | Tasks should reach available workers without granting their requester ownership. |
| Move a ticket (`/api/move`) | **Remove:** Metaform should allow ordinary ticket moves and retain dependency validity and any deliberate hold-release instruction. | Workers need coordination access without accidentally releasing work deliberately held back. |
| Edit a ticket (`/api/ticket`) | **Remove:** Metaform should allow assigned ticket edits and retain exact identifiers, dependency validity and recorded change history. | Ticket coordination needs record integrity rather than a privileged worker name. |
| Distribute tickets (`/api/distribute`) | **Remove:** Metaform should allow assigned ticket distribution and retain actual ticket and scheduling constraints. | Assigning ordinary work needs no privileged worker identity. |
| Release deliberately held tickets (`/api/unhold-all`) | **Replace:** Metaform should require an instruction covering the intended hold releases and accept it through any worker. | A bulk release must not erase deliberate holds outside the current task. |

The web restriction does not cover worker shutdown commands.
Entry 12 still requires the separate shutdown protection.

## [ ] 29. Metaform limits board wipe and restore commands

- **Now:** Metaform excludes board wipe and restore from the agent tools.
- **Recommendation:** Metaform should accept your actual board-wipe or board-restore instruction through any worker. Metaform should retain the named board, selected backup and existing restoration checks.
- **Why:** The named board and selected backup identify the destructive change you requested.
- **After removal:** Workers could request board wipe and restore through the agent tools.
- **Pros:** Workers could follow your specific instruction through their existing tools.
- **Cons:** A worker could erase or replace the wrong board.
- **Source:** [Board wipe and restore](../../src/metaform/modules/map/__init__.py#L1784).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Wipe a board | **Replace:** Metaform should accept your exact board-wipe instruction and keep a recoverable backup. | The named board and recovery copy protect data without a worker ban. |
| Restore a board | **Replace:** Metaform should accept your exact restoration instruction and check the board, backup and conflicting newer records. | A restore must not replace unrelated work recorded after the selected backup. |

## [ ] 30. Metaform blocks agent answers to ticket permission questions

- **Now:** Metaform can refuse a worker's attempt to close a ticket permission question.
- **Recommendation:** Metaform should accept your actual ticket-permission answer from any worker forwarding it. Metaform should preserve the question identifier and its first recorded answer.
- **Why:** Metaform needs your actual answer, rather than a particular worker carrying it.
- **After removal:** Workers could close these questions through the affected path.
- **Pros:** Workers could record your answer without another interaction.
- **Cons:** A worker could close a question without receiving the answer it requires.
- **Source:** [Ticket permission answers](../../src/metaform/modules/map/storage.py#L494).

## [ ] 31. Metaform limits sending work to Paperclip through agent tools

- **Now:** Metaform can block this send through the agent tools. Workers can already use the terminal without that restriction.
- **Recommendation:** Metaform should remove the extra Paperclip sending ban through agent tools. Metaform should keep company-access checks. Metaform should reject closed or assigned tickets.
- **Why:** The terminal already permits the same send without this extra worker restriction.
- **After removal:** Workers could send work through the agent tools without this extra setting.
- **Pros:** Workers could send work through the tools they already use.
- **Cons:** Workers could start outside work or incur costs without suitable action checks.
- **Source:** [Paperclip sending](../../src/metaform/modules/paperclip/__init__.py#L446).

## [ ] 32. Metaform blocks workers from paid phone actions

- **Now:** Metaform rejects worker requests for paid phone calls, texts and call connections.
- **Recommendation:** Metaform should remove worker-session refusals from assigned phone calls, texts and phone-bridge startup. Metaform should retain the configured account, enabled-phone checks and twilio_owner_numbers recipient list.
- **Why:** The existing allowed-number list protects recipients without requiring a privileged worker.
- **After removal:** Workers could request paid phone actions.
- **Pros:** Workers could carry out permitted communication without requiring another worker.
- **Cons:** Workers could contact the wrong person or spend money without suitable limits.
- **Source:** [Paid phone actions](../../src/metaform/modules/twilio/__init__.py#L307).

## [ ] 33. Metaform limits phone-service address repairs through agent tools

- **Now:** Metaform can detect the wrong address for receiving call and text events. Metaform can refuse repairs through the agent tools.
- **Recommendation:** Metaform should allow phone-service address repairs when the destination matches the project's current phone service. Metaform should retain account authentication.
- **Why:** The expected service address determines a correct repair, rather than the worker's label.
- **After removal:** Workers could repair that address through the agent tools.
- **Pros:** An informed worker could complete its diagnosis and repair together.
- **Cons:** A worker could send phone-service events to an unintended address.
- **Source:** [Phone-service address repair](../../src/metaform/modules/twilio/__init__.py#L768).

## [ ] 34. Metaform hides phone-service checks from some workers

- **Now:** Metaform limits some phone-service checks by worker type.
- **Recommendation:** Metaform should expose phone status and connection checks to every worker. Metaform should report missing setup instead of hiding these checks.
- **Why:** Reading diagnostic information does not authorize paid phone actions.
- **After removal:** Workers could discover and use these checks.
- **Pros:** Workers could diagnose phone-service problems without starting a specially named worker.
- **Cons:** Workers could receive account information unrelated to their task.
- **Source:** [Phone-service tool visibility](../../src/metaform/modules/twilio/__init__.py#L780).

## [ ] 35. Metaform no longer restricts ticket claims through the old claim function

- **Now:** Earlier changes removed the old ticket-claim function. A separate agent-name check remains at worker startup.
- **Recommendation:** Metaform should keep the old claim restriction removed. Metaform should apply entry 21 to the separate agent-name restriction.
- **Why:** A worker name provides no protection against invalid tickets or conflicting changes.
- **After removal:** The removal eliminated this old restriction on ticket claims.
- **Pros:** This old restriction no longer prevents an informed worker from taking work.
- **Cons:** Metaform loses no necessary protection if it keeps ticket requirements and conflict checks.
- **Source:** [Current ticket operations](../../src/metaform/modules/map/__init__.py).

## [ ] 36. Metaform no longer requires your message before ordinary ticket coordination

- **Now:** Metaform can record your message when available. Metaform does not require that message for ordinary ticket coordination.
- **Recommendation:** Metaform should retain ordinary ticket ordering and dependency edits without requiring a user-message record. Metaform should record the actual editor and reject invalid dependencies.
- **Why:** Valid dependencies and recorded changes protect coordination without requiring another message from you.
- **After removal:** Workers can coordinate tickets without presenting a message from you.
- **Pros:** Workers can arrange ordinary work without repeatedly involving you.
- **Cons:** Workers could change ticket order against your stated priorities without separate priority checks.
- **Source:** [Ticket coordination](../../src/metaform/modules/map/__init__.py#L1642).

## [ ] 37. Metaform exposes map questions only through the terminal

- **Now:** Workers can create map questions through the terminal. Metaform does not expose that command through the agent tools.
- **Recommendation:** Metaform should expose map ask through agent tools using the existing command's title, reason and target fields. Metaform should record whether the question came from a worker or you.
- **Why:** Workers should reach the existing question operation through the tools already available to them.
- **After removal:** Workers could create map questions through the agent tools or terminal.
- **Pros:** Workers could ask map questions through their existing tools.
- **Cons:** Metaform would need to maintain another way of receiving commands.
- **Source:** [Map question command](../../src/metaform/modules/map/__init__.py#L2511).

## [ ] 38. Metaform exposes map-finding approval only through the terminal

- **Now:** Workers can approve a map finding through the terminal. Metaform does not expose that command through the agent tools.
- **Recommendation:** Metaform should expose map approve through agent tools using the terminal command's existing finding checks. Metaform should record who approved the finding.
- **Why:** The existing finding checks remain valid through either way of sending commands.
- **After removal:** Workers could submit that approval through the agent tools or terminal.
- **Pros:** Workers could submit approval through their existing tools.
- **Cons:** Metaform would need to maintain another way of receiving commands.
- **Source:** [Map-finding approval command](../../src/metaform/modules/map/__init__.py#L2598).

## [ ] 39. Metaform requires different source information on its page and other tools

- **Now:** Metaform demands a source for a glossary term outside its page. The page does not demand the same input.
- **Recommendation:** Metaform should keep the source requirement and apply it to the page too. Metaform should accept an original instruction or map record as the source.
- **Why:** A source lets other workers verify a term regardless of who entered it.
- **After removal:** Workers could add glossary terms without supplying a source through the agent tools or terminal.
- **Pros:** Workers could avoid unnecessary input when Metaform already knows the source.
- **Cons:** Workers could add terms that other workers cannot verify.
- **Source:** [Glossary source checks](../../src/metaform/modules/map/glossary.py#L225).

## [ ] 40. Metaform gives intake workers special control over the displayed project

- **Now:** Metaform gives intake workers an exception through the agent tools. Workers can already request navigation through the terminal.
- **Recommendation:** Metaform should remove the intake-only navigation exception from web start. Metaform should move the displayed project only when the current task requests that navigation.
- **Why:** Your navigation request determines the displayed project, rather than a worker's intake label.
- **After removal:** Every worker could request page navigation through the agent tools.
- **Pros:** Workers would no longer gain page control from the intake label.
- **Cons:** Workers could unexpectedly change the project you see unless Metaform checks navigation requests.
- **Source:** [Displayed project changes](../../src/metaform/modules/web/__init__.py#L355).

## [ ] 41. Metaform requires your instruction for selected map operations

- **Now:** Metaform checks your instruction for creating, switching, removing or rewriting saved maps.
- **Recommendation:** Metaform should replace the general worker restriction with the four map-operation rules below.
- **Why:** The exact map operation determines its data risks, rather than the worker's label.
- **After removal:** Workers could request these map operations without this instruction check.
- **Pros:** Workers could perform assigned map operations without repeating decisions elsewhere.
- **Cons:** Workers could activate the wrong map or remove information you meant to keep.
- **Source:** [Map operation declarations](../../src/metaform/modules/map/__init__.py#L2401).

### Individual command gates

| Control | Gate recommendation | Why |
| --- | --- | --- |
| Create a new active map (`map add-base`) | **Replace:** Metaform should accept the actual new-map instruction through any worker and retain valid names and map-switching information. | Creating an active map changes the destination for later work. |
| Switch the active map (`map activate`) | **Replace:** Metaform should accept the actual switch instruction through any worker and retain the exact existing map target. | Workers must remain on their original maps unless their assignments deliberately change. |
| Remove a saved map (`map remove-base`) | **Replace:** Metaform should accept the actual removal instruction through any worker and retain backups and active-map refusal. | These checks preserve recoverability without reserving the operation to a worker type. |
| Rewrite a map while keeping the original (`map collapse`) | **Replace:** Metaform should accept the actual rewrite instruction through any worker and retain the original map and stable object identifiers. | Rewriting a map into one layer must not discard evidence or detach existing records. |

## [ ] 42. The sentinel instructions prohibit file changes

- **Now:** The sentinel instructions tell an investigation worker never to change files.
- **Recommendation:** Metaform should replace the sentinel's permanent file-edit ban with the limits of its current assignment. Metaform should let the same worker implement a later explicit repair task.
- **Why:** A later repair assignment changes the worker's task without requiring a replacement worker.
- **After removal:** The instructions would no longer prohibit a later repair assignment for the same worker.
- **Pros:** The worker could use its investigation findings without transferring the task.
- **Cons:** The worker could edit files during an investigation unless the current assignment still prohibits changes.
- **Source:** [Sentinel instructions](../../src/metaform/skills/sentinel/references/procedure.axiom#L154).

## [ ] 43. The user agent's instructions require new workers for selected transfers

- **Now:** The instructions require a new worker when transferring work. The instructions also require an architect after planning.
- **Recommendation:** Metaform should remove mandatory new-worker transfers and the mandatory architect-agent transfer from the user-agent instructions. Metaform should allow existing workers to load architecture or implementation skills.
- **Why:** Mandatory transfers discard useful working understanding without guaranteeing better work.
- **After removal:** An existing worker could continue instead of starting another worker for these steps.
- **Pros:** Workers could retain useful understanding and avoid repeated explanations.
- **Cons:** A worker could miss useful independent review unless Metaform preserves review requirements.
- **Source:** [User-agent instructions](../../src/metaform/modules/tasks/resources/user_agent.txt#L5).
