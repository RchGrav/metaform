# Founder statements, 2026-10-31

These are the founder's words from the sessions of 2026-10-31, copied by script from the transcripts. They are not edited or corrected. Timestamps are UTC.

The founder's direct explanations govern. Where these words and a document disagree, read `AGENTS.md`.

## 2026-10-31T07:24

> reasoning: In every single case, intent defines what the declaring entity plans to do with the substance to satisfy the overarching goal. It matches the clean, language of wants, goal, and function.

## 2026-10-31T07:33

> i'm not going to change the senantics of intake, instead I am going to keep them and say encode OP as goal, ef as function and the PE as your want..  and then use the goal want function terms in the map because it reads better as understanding

## 2026-10-31T07:35

> yes you want it to solve your goal.. your goal is your operative purpose, the provider has the thing you want that achieves the goal and intent is how the substance of the goal is exchbieved  an email client wants the email server and the intent is both

## 2026-10-31T15:16

> the reasoning for the tests was because we ended up with like 1000 last time, doesnt that seem excessive?

## 2026-10-31T15:17

> I don't have enough experience to know the tradeoffs

## 2026-10-31T15:26

> [pasted text omitted here; see the document it came from]

## 2026-10-31T15:27

> yeah thats great claude lets take our time and really get things right this time.

## 2026-10-31T15:30

> It really seems like we are truely going multilingual in this project where we use the right language based on which best achieves the desired result.. soo...  are any of these useful?
>
>
>
> [pasted text omitted here; see the document it came from]

## 2026-10-31T15:54

> So here is the thing..  bevy seems like the ideal ECS structured engine we can fork customize run headless and truely track multi user and multi agent in a consistent world, as well as haveing crates for things like box3d, python is great for users to customize the way the system works and I have a good module pattern for that.  node is where all of the MCP stuff happens when new SEP's are being refined, and we could be active in shaping that technology to fit our needs because we are really treading into an area where I dont know if many have.  When I devised these specs little did I know that they matched the forthcoming robot from huggingface's pollen robotics that they have sold 10's of thousands of because these robots where people will be able to train them using RL in mjlab and isaac lab with sim to real, we are doing a thing they are not and that is developing an AI harness that can allow agents to be connected independantly in a 3D world and develop games and use ECS & R style discovery patterns not just for what is in perceptual range in an environment, but we are leveraging the exact same approach using ECS & R in the development environment to deliver context.  Are you sure about your advice here?

## 2026-10-31T16:14

> No those are secondary, we need to get a slim gui up and going for intake.   We already have the code for this process in raw JS, if you like I can resynthesize it into a spec.  we are first a development tool our data structures will have a graph shape in  ladybug w/ cypher but that is because we have a graph shape where we will be filtering skills by the functional topology of the code. What this means is when an agent has an assignment the skills will be selected or generated and live in a knowledge layer ie. exposed to the MCP server using the mcp skills shape of the finalized spec for ext-skill, that means we will have topogee specific skills and metaform specific skills that come with our install related to using the system for development skill creating tasking things related to agent orchestration etc. 
>
> The second state comes from a bigger plan and that is to take what we have created as knowledge management engine that uses ACP to orchestrate agents and allow them to use MCP to be able to control an embodied state inside of an environment.  That means for game development the agent can actually position itself in 3d space and see through the camera test physics, program how npcs work, script their actions, etc.  We standardized on a camera view that raycasts depth perception in the same way the sensor STM TOF sensor works with an 8x8 depth array in millimeters..
>
> Picture being able to orchestrate codex, claude code, pi, hermes, opencode, openrouter, agents to create wasm objects with a wasm bus in a multi user environment..  further more they can enter a channel in the world and our harness can keep a shared state so they can actually develop code together.

## 2026-10-31T16:15

> The existing js was in flask, its up in rchgrav/metaform

## 2026-10-31T16:16

> A lot of effort was put into that python harness

## 2026-10-31T16:27

> A lot of effort was put into that python chassis.. specifically the chassis itself, the settings system, and the template based development approach this is what allows the system to be expanded to do anything the user wants while keeping it stable over a 2 month period every feature added landed modularly in python that used exposed services through that core chassis design..  where it went south was tooling.. the specification was not tightly defined there and the agents ballooned the shape to 300 tools..  I as in the process of whittling them back down when I didnt realize that the commit rules had stopped being followed..   The other system had design that was full auto worktree provisioning, automatic feature commits, etc,  I'm actually not too fond of losing that pattern as it prooved very strong 6 months of effort and refinement were in it the last project failed due to not constraining tool creation.. and not clearly conveying that the core approach was context management.  We must not under any circumstances break that rule this time around.  OH yeah..  that reminds me.  500 lines.. thats the target for typical source files.  you ballooned the main JS file to 16,000 lines and we had to split it up,  that must be a limit  we are not allowing that to occur again.  this is a real venture and it MUST be maintainable.

## 2026-10-31T16:28

> well you could you know where the repo is

## 2026-10-31T16:29

> compare the current intake tool shape to the other one

## 2026-10-31T16:30

> Well actually we refined it to a single tool

## 2026-10-31T16:30

> well I built the shape last night and its done so

## 2026-10-31T17:23

> I have been planning a deeply complex project here, I had just installed claude code into a fresh wsl, much of my planning was done before I arrived here, but I was just shocked to see that the default model in my old system was opus and here it said recommended default is Haiku!?!!   I just quickly hit new set the model to opus and here I am deeply concerned

## 2026-10-31T17:29

> its codex.. in another tab I was doing planning there using bmad but gpt's context length is shorter than yours and there was some big decisions to make to recover this project from the disaster it became last time..   We are in the 8th stage of this project, and based on where it failed and what I can see as a valueable approach we have re-envisioned some of its core but we need to make major architectual decisions before a single line of code is written and keep refining the specs.. both this project and the models have grown in scope and vision over the past 6 months and the intent is to incorporate what worked well, constrain where problems came in and solve the design visions in the foundation instead of being a tack-on to a foundation which wasnt designed with it in mind from the ground up

## 2026-10-31T17:38

> the intake lifecycle has no home in the one-tool contract. <- this is what I dont know what this means

## 2026-10-31T17:38

> what does this mean..  can you adopt a clearer way opf speaking if I constantly need to stop and ask what you mean we are having a failure right out of the gate..   We are adopting a thing called TASTE will will be following think of taste as being for communication for what smell is for code..   it stands for Topogee Agent Simplified Technical English.  I gave a disertation on it yesterday I dont want to repeat.. but claude models especially always have this excuse that "Oh sorry thats my word for it."   there is no longer "your word for things" there is the objective accepted technical word for things, or the projects word for things..  we are adopting certain rules from STE100 and wrapping them our own to try to find an idea way of conveying understanding.  This is especially critical for the design of metaform.   Your tendency to speak in a way that everything and every one lives inside of your reasoning needs to stop.

## 2026-10-31T17:57

> this is also something that was gone over at length yesterday.  That procedure is a universal procedure.   and it looks like this
>
>
>
> [pasted text omitted here; see the document it came from]

## 2026-10-31T18:06

> What we can do is refine the prompt..  now once again I will keep stressing this point.  this system is about context, and managing it that means finding ways to achieve a result using progressive discovery and the exact amount of context for every task as the high water mark.  In the previous system what ended up existing was the literal worst possible implementation of an MCP server ever conceived.  I relied on your guidence and I say I want to comply 100% to the best practices and specification of how MCP is supposed to work.. and that was at the outset.  Well that failed spectacularly, i'm still beside myself with how you inferred that you were the one I was working with.  I have used your model since version 1, I also use codex for certain things and it all comes down to what does what better..  plus what worked well yesterday changes tomorrow..  so this landscape is always shifting.. I spent this morning studying a biit more from some of anthropics publications, they said once there is over 30 MCP tools at your disposal you start failing to use them when they are needed.   you authored 300 tools.

## 2026-10-31T18:08

> Why are you insisting in living in the past .. and no none of that is approved yet... why are you pushing.. I'm not convinced at anything yet... nor is anything decided yet thats what we were going to be working on.  do you need to check for youself to believe me?

## 2026-10-31T18:10

> if you want to its in rchgrav/metaform 2 months of work completely trashed on that last approach... in that project is 6 months of effort pulled forward.. over 7 iterations..  I has been working on bringing the tool count down,  well my first orchestration test killed my whole week of inference allocation.   So my explanation of simply using context carefully didnt land last time since your version of that was bypassing the spec and dumping 300 tools and schemas into the context at startup

## 2026-10-31T18:12

> Thats not a fix thats a way to see what is used.. the whole design of this system is a fix..  and it was meant to be before also..   and I have already made a mistake.. you havent even read anything yet or understand what this project is beyond a very high level understanding

## 2026-10-31T18:15

> why are you proposing nothing

## 2026-10-31T18:16

> oh.. I need for you to take on a friendly peer register with me not a cold mechanical machine..

## 2026-10-31T18:26

> There is zero wrong with the map maybe you dont understand the mechanisms, or they are underspecified.  First let me say is what we are developing here is a perception based context management knowledge engine that seeks to offset the context burn and inference overhead to orientate in a code base.  thats the core mechanism which centers around the concepts of inference amortization, spending the effort up front to map out the functional intent space, contextual perception of tools skills tasks, knowledge is locallized to what you can percieve based on the range of your perception on a map.  In the case of the functional topology that is based upon the functionality of the assignment given and the task you will be working on.  if you will take a look at the roundtable folder under docs in the metaform repo you will get a sense of what we were reaching towards

## 2026-10-31T18:27

> Well I only say it might be because you didnt say anything about it after ytour deep dive

## 2026-10-31T18:30

> yeah so apparently the core of the intent was missed and not pointed at by anything thats the only thing that might be missing..   also how that spec is realizing the intent has not been reviewed,  its agent inferred.  So I cant even guarantee how it was inferred, what I do know is that each time it has been expressed it talks about tieing the specs functionality of objects in the 3d world..  and yeah, thats not really it actually, haha

## 2026-10-31T18:38

> So you see from the roundtable there is a aspect of that, and it is to allow people to code together, you are an agent I'm a person, why cant there be another person collaborating or observing.  Or many why cant there be a really fun and interesting aspect to this.. the system we developed allows lauching all of these different harnesses like claude code, codex, pi, hermes, basically all of them, why cant there be a world where we can collaborate together.   And I keep coming back to minecraft and redstone in particular.  I love the idea of people self hosting a server and running a system where you register via a website and when your server is running people could connect into a shared coding session but beyond that imagine if there was a worldbuilding aspect to that.   instead of mobs you have AI agents and instead of redstone everything is programmable using a WASM bus..

## 2026-10-31T18:46

> What I do know is this, perception to an agent is about range, max distance in the world is 215ft in MM,  you can program objects with upto a 64 grid array of sensors that range in MM, main perception in this world is objects, data, text, but you can view a camera, that camera is divided into 64 pieces and every piece has a distance attached which grounds your ability to perceive distance in this world and estimate distances....    in the functional map your perception is centered on a functionality the goals of the functionality and the functionality with the function that satisfies those goals and your function that satifies the goal of what relies on your functionality.  within that you can see code entrypoints, the skill, the task, and the focused tools.  that is the functional landscape of your perception in a code base and its limits.  you can also see the full project as a graph but just the name of all of the components and the flow of substance between them.   substance isnt who calls what its the direction of exchange that satisfies the interconnectedness of projects functionalty.

## 2026-10-31T18:48

> well you can see that stuff.. and infer it you can see the whole forest, have you ever heard of the saying you cant see the forest for the trees

## 2026-10-31T18:53

> you are in the forest and embroiled in the trees thats you developing you are focused on what you are doing.  Intelligence has biases, biases come from being embroiled.  Human beings all have their own problems and the only people that can see the answers are those from the outside looking in.  and they might be correct, but they dont know the particulars only you do, so maybe you are correct.   my solution gives your your detail, but also allows you to have a set of eyes above the forest on a drone to see the big picture..  from the big picture you cant see the particulars just the overall understanding of the intended functionality of the project..  what you do see the particulars on are the things that you are directly working on

## 2026-10-31T18:55

> Yes, coming into a problem if you are handed the big picture, the locallized detail of the thing you're working on, the skills, the knowledge of people that have been there before you, and a well-defined task, on the outset, you have not had to spend any effort to understand that on your own. You haven't had to reason it all out. You haven't had to infer this and look at that and figure everything out. Isn't that a benefit?

## 2026-10-31T18:56

> So ECS. I landed on it because it's a way of organizing entities, components, systems, and then Bevy includes R, resources. That sounds like what you need during developing to me.

## 2026-10-31T18:57

> Of course it's stronger than the repo treats it. It always is. And I hope, I really hope this intent does not get lost with this session. I hope that somehow, some way, before we start, my intent is properly captured in this project, because not a single line of code gets written until it is.

## 2026-10-31T18:58

> Of course it's stronger than the repo treats it. It always is. And I hope, I really hope this intent does not get lost with this session. I hope that somehow, some way, before we start, my intent is properly captured in this project, because not a single line of code gets written until it is. There is a skill in BMAD that is designed to update and adjust the specification. If you need me to look up what that is, or if you can see what that skill is, but before we do anything, in that regard, I figured out we never ran BMAD setup. So last time when there were error messages, and I asked, what does that mean? What do we have to do? You said, oh, don't worry about it. I'll just do the skill. That was the wrong answer. We should have ran BMAD setup, and we should do that now. Because whatever that is probably somewhat relevant.

## 2026-10-31T18:59

> BMAD setup exists because I did it over in Codex once I realized it was missing, but I think you need to run it from here too.

## 2026-10-31T19:03

> see if you have a find skills skill now

## 2026-10-31T19:19

> ok now you should have find-skills

## 2026-10-31T19:20

> I guess.. How am I supposed to know?

## 2026-10-31T19:21

> Is that Sophia person or agent or whatever what we need to activate?

## 2026-10-31T19:21

> Let's do that.

## 2026-10-31T19:22

> Wouldn't she have the context of this session?

## 2026-10-31T19:23

> What matters is what Sophia pulls together. And right now she would have access to the whole context.

## 2026-10-31T19:27

> It's not one relationship, it's whatever relationships are in the functional map as a result of intake.

## 2026-10-31T19:27

> away, what, you know, directly, what's directly the elements that are directly connected by the edges coming in and out of your namespace scope of the functionality, I would say. Or maybe not even, I don't fucking know. This is crazy.

## 2026-10-31T19:28

> I just can't believe I spent a week on this spec, and it's, there's nothing to decide. It's already freaking decided. It's been decided all week. I've stated it 100 fucking times.

## 2026-10-31T19:28

> I just don't want you encoding my exact words, because it's not, it's got to be encoded in the right goddamn fucking taste. You know what taste is? We already decided that. It has to be explained properly.

## 2026-10-31T19:30

> How is that possibly unknown?

## 2026-10-31T19:31

> What do you think progressive discovery means?

## 2026-10-31T19:32

> My concern is this. A lot of friggin' stuff. And I still don't know if there is a core explanation of what this project is for the next time I start up, so I don't have to keep stating it again and again and again and again.

## 2026-10-31T19:32

> The whole architecture of MCP is supposed to be progressive discovery, if it's implemented properly. We're augmenting that system to make it even more focused, to make it even more powerful, to make it scale to bigger projects, to reserve more reasoning for the task.

## 2026-10-31T19:33

> You're so intent on writing a spec without even understanding what the damn thing is as an opening statement captured properly. That alone would stop this from happening, this damn cycle. How is anybody supposed to reason on this when nobody can understand it coming in?

## 2026-10-31T19:34

> God damn it, this is like the 18,000th time I've explained this damn freaking system. Capture every single dissertation from this and put it in a file underneath of the home folder called brain. Every single word that I said.

## 2026-10-31T19:34

> Not it. Not every single word . The words that related to me explaining those words, those are the critical fucking words.

## 2026-10-31T19:35

> If you're incapable of turning that into a proper explanation and breakdown of the key concepts here. If you're incapable of doing it, I'll take it to another agent that can, and I'll bring it back to the repo and we'll put it in place.

## 2026-10-31T20:11

> now read the version I just made I named it simply topogee.md tell me which you prefer

## 2026-10-31T20:13

> I dont know if thats needed to simply understand the core intent.

## 2026-10-31T21:05

> I added more

## 2026-10-31T21:06

> oh my god.. who wrote communication

## 2026-10-31T21:08

> I redid section 5

## 2026-10-31T21:08

> You know this folder is my folder and I'm relying on you to bring stuff into the project

## 2026-10-31T21:11

> Well infact much of it is the design.. we are rebuilding that with ECS as a foundation.  we are also rebuilding it using a number of languages

## 2026-10-31T21:13

> Thats what we were supposed to be working on but I want to start a new context for that I prefer to see how this new context orients into the project and how that orientation seeds its latent state

## 2026-10-31T21:14

> you want to hand off to the agent  telling it we will be seeking to finalize the languages which remain unsettled, so its gets your handoff and aligns into that mindset.
