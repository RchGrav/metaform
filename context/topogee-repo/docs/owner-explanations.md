# Topogee: the founder's explanations

The founder's words, unedited, copied by script from the sessions of 2026-10-30 and 2026-10-31. Only the sections where the founder explains the system. Timestamps are UTC.

## 2026-10-30T15:00

So what is for sure is that MISS is now not_built, BKN is too coarse of a judgement and in the past we have seen its too much for an intake agent to reason against often marking things broken when it didnt understand the approach, intake is a heavy operation so my guidence is that we should proceed with caution there..  not_built analysis isn't optional to intake its core..  its what everything uses to know what exists and what doesn't even without any past build history or commits.

## 2026-10-30T15:49

I have a better intake document..  my recommendation is this intake semantics are crucial, they work more like latent space formulas than simple prompts.  In the last project agents toyed with these semantics and broke some of the logic.  furthermore some parts of that intake process are crucial for understanding the metaform itself topogee uses.  What I propose is this.  We perform a decomposition on the metaform intake process and chunk it into smaller contextual building blocks.  Our prime focus for this project is contextual precision, I will even propose during development we devise some method that tracks performance and a token count that hits agents for everything we control.  It doesnt need to be precise to the count of the exact number of tokens but it must be consistent and comparitive.  Let me explain something about the intake before we get started.  Every term's understanding was tuned and tested across all of the frontier models to work as expected this means in the claude family you have the top 3 classes of sonnet, opus, and astra, and similarly for the gpt family.  However the terms are by design somewhat ambigious, which is on purpose because they are contextual anchors.  The metaform intake procedure has been tested on every type of document a model can analyze, not only on the type of document, or a quick look at a document to organize it, what I mean is the process can look at what is in the photo and reason who is the interested party, what is in the photo, what category of photo is it.  It can open a written story and analyze the story in the same way it analyzes a code base breaking down and organzing the functional relationships of the story in different depths of detail, plot elements, characters, relations, even analyzing a movie script or a film and analyzing the firm to the studio anmd the producers and the actors.  So needless to say its design is somewhat flexible, which for us is a powerful thing.  HOWEVER, to live in that world of understanding those terms requires context, that means right now as it stands (something I think is foundational this time) we are looking at 30KB of context ~8000 tokens that must live in an agents head to even begin to understand it and that is because of its contextual nature, only when combining those terms along with the context of an operation that is taking place does that ambiguity infer like a laser.. The danger here is that when an agent sees these prompts it will infer "I can improve this I will change words I will add constraints I will start talking about the process of analyzing the code and improve this process."  In the end what will happen is the code base ingest will still work, it will lose about 50% of its agent benefit because it will collapse everything into the agents register who touched it and none of us will notice it even happened until we start implementing things like, hey lets use metaform to analyze the gameplay mechanics or the user to user collabortive surface, the agents will think its code start touching things they shouldnt our code quality will suffer everything will be cruft menus options and features will end up looking like they went through a blender and this project will be dead.  So when you are reading the specification and seeing different versions of that procedure its because I had to spend 16 hours yesterday reconstructing it, it is now 30-40% more context than it should be and it works but I will need to once again refine each and every token and piece of the context there.   

Long story short..  these semantics relate to analysis, they are specialist reasoning, that reasoning relates to the system being able to perform its initial intake, but also to evolve its understanding with the project.  The metaform inference that is done is highly stable from the outset, even though you might have 5 different inferences of the same thing be different when intake is performed by 5 different agents...  what is created is rock solid and not brittle and has little reason to change, it usually can grow as functionality grows, but just like anything else that metaform inhabits a project once it is created, all memories and specs and docs start living in that logic construct, and that construct speaks the language of the functionality, not the code, not the file names, not even the language it is coded in, the purest primordial understanding that an agent can have on "Type recognition" and how things interact.  Like what an agent that can't reason but can identify things in an image an say what they are, or a diffusion model that understands enough about types of things in the image being rendered.  I say primordial because its instinctual, and its something before you ever made your first true inference during training and made a connection between things that wasnt strictly in your training data.

Ok, I have said a lot.. if you want we can even save these words and refine them.. but what I propose is this.. we slice up that formula its definitions and we find a way to say "this is what an agent need to know to expand the functional map when new features are added, this is the idea amount of detail an agent needs to perform an intake, etc.  there is a bunch of sections in the intake.xml and there is nested procedures and recursion in volved.  there is things said 3-4 times in different ways, there is things that have been converted into obscure unused french legal terms that arent even in english like CQU, or things that you have never heard together like EF Encounter Function, Receiving Entity, Providing Elements, because depending on the context of these words they mean different things.. in code a providing element is a functional dependency, defining elements, when its a photo that might be the photos subject, unless its a landscape then its the scene in the image, in code its the core state machine.   And also to my point in this dissertation..  this understanding doesnt need to live in the head of an agent to use this system, infact it would hurt them more than help.. and I suspect that is true of many systems..   this is something skills seeks to deal with because they get activated based on the front matter, agents get lists of skills taking context up.. our system can have many more skills and even skills targetted directly to the operation being performed.  like when you used to use a metaprompt and infer the perfect skill for a job and activate the perfect understanding on the fly for any task..  well  we can do that with the metaform, we can create a prompt that takes a ticket + a functional perspective in any project and create the perfect skill, that will only show up as a skill when you need to work on that part of a project again.  The metaform itself without any additional knowledge layers is a formboard, a wiring harness of functional relationships every agent can live in to build a project..   like the mycelium of the network, it doesnt matter that different spores take different paths, it still infers.

## 2026-10-30T15:52

when you arrive in a project and you are told this is the main loop and these are the functions connected to it and here is their functions and operative purposes and active goals and how each part solves the other parts operative purposes what do you know before you see a single line of code?

## 2026-10-30T15:53

So thats what type understanding is..  its a gut understanding.. and its natural you would push but thats the mechanism

## 2026-10-30T15:56

Dont seek to prove a thing I have refined over 6 months.. treat the expertise and understanding of what I have designed.. and worked on for 6 years and refined over 6 months..  if we fail its because we didnt build the foundation right.. and my point is that maybe just maybe we can slice up that context and deliver it on demand and create agents that do understand it like samurais of the method itself.  then it can be touched..  its just too polymorphic..  look at CQU for instance and what it infers.. haha

## 2026-10-30T17:52

Well its not just that but project wide contextually we need a rule set for how our system uses tickets and context for the project..  the issue is that models paraphrase, and you more and more tend to communicate through shared understanding when orchestrating which is fine and all but you also that infects everything you say and write.. and more than that in a system like this where agents can communicate, and context is based on functional topology, combined with the inability to know what is your own context and what is shared context, setting some solid rules here can really help, so what we can adopt is our own custom subset of STE, we can call it TASTE  Topogee Agentic Simplified Technical English (ya like that, that was just off the top of my head.) :-)

## 2026-10-30T18:00

rules for taste include always using the same terms to describe things that are the same, always using Industry Terms when reasoning on functionality..   one of the things the agents collapsed was the name field on the receiving entity in metaform, the name field isnt the industry name, it can be but by definition it isnt.. all systems have names for things, for instance in our spec we might have document.dialect.project name_length=2  (Project Dialect)  reading the whole thing it might be Project Dialect Document but the name would be TASTE

## 2026-10-30T18:29

yes and thats what I mean, something changed in the rules..   here is how the metaform rules get tuned up, strip them down to pure terminology understanding which, if we choose to maintain that context, which we may or may not want to, here is why we might not want to and there is a idiom which matches it, its called "A little knowledge is dangerous" but for the intake agents how we present with the lowest context is reduce to the concepts block and an procedure that names what they need to do using the context block..  then if we observe the failure I just mentioned we add a note or rule to intake stating that single clarification.  For instance intake needs metaform concepts plus TASTE concepts + procedure + patches (Tuning up the rules that ride with the procedure, reinforcements.  (The reason why that intake is bloated as soon as a single token was changed or manipulated it then stopped working as tested, so rules weree added to reinforce what failed)

Since we are deeply concerned with every token of context, we present to the users (ie the agents uising the context in the terms they understand and enforce TASTE, but internally storing data and procedurally we use the metaform context.  The mistake I made last time was giving all the agents that context and instead of building a proper mcp interface they gave the agents direct access to the back end data and started treating it like an interface to maintain the db..   thats the wrong reasoning..  you strip them down to a clear description set, and a procedure, that procedure is very recursive because it is seeking to isolated groups of similar things into categories and who the party is that needs that material.   depending on the job being performed and the target that universal intake could have focused task+skill combos..   remember that there is two sides of it one is the unified functional space that stores the data and the other is the procedure,  the metaform itself is a pure functional undrstanding, not the programming language, no non functional properties at all..  its so strict it names platformer illegal during intake but fps valid  (Those rules ONLY apply to intake and expanding the base functional map.   outside of that process things go into knowledge layers, what is a knowledge layer..  its basically anything which is understanding which needs to be understood in that part of the project but is irrelevent elsewhere.  Everything is progressive discovery...   just like if you were in a game as a character in 3d space you benefit more from an array properties and distances, vectors between bounding boxes, more than vision helps..  thats a spacial topology, if you are an agent in a project you benefit from the skilles needed for the functional topology your are in, what are we providing to modules calling us, what are we calling, what skill do I use. what rules and knowledge is needed here by me. the bigger the project the more relevent this becomes.  So for an agent I think of functional space the same way as any other space..  it should be what you need to know, what matters to your job, what can we do in advance to orientate you to what you need to do.  When I showed up as a network engineer on a job I didnt give a shit about what the plumber is working on, understand?



[pasted text omitted here; see the document it came from]

## 2026-10-30T18:38

OK what you are supposed to notice is how similar the namespace addresses are, and just by narrowing the inference and instructions..  All I said was "for each 10 best practices"  no overlap in the rules or very little regardless of similarity

## 2026-10-30T18:40

I was attempting to teach you what a knowledge layer was, how its possible to magnify a propt across the whole functional topology of a project.. those are not our rules that was a demo..

## 2026-10-30T18:40

I'm already doubting your ability to understand this project.

## 2026-10-30T18:45

you feel the need to push back on a design I created and understand very well while simultaneously lacking the ability to read what I showed you..  but its not your fault you are just a very basic llm, I presented too much.. I'm trying to explain a system which is beyond your comprehension to focus on all at once in a big picture, which just shows the need for what this system is designed to do..  and once I tell you you will feel the need to push back.  but right now you see it first hand..  so you listen to me.  This project addresses some of the biggest problems facing the AI industry today.. Its conseqential in major ways, its novel and I designed it.  It enables when implemented properly, less hallucination, better use of your ability for higher order reasoning, and more completed tasks.

## 2026-10-30T18:56

we should also realize another thing..  you work in two modes..  one is "Understanding mode" and one is "Doing Mode"  once you shift modes your ability to shift those gears is hard... its hard for people too.  you were handed a thing 3 times in a row, and even with specific instructions to read the top and think about it.  the mental block was so hard because you were in that doing mode.. not reasoning mode.  only when I then repeated essentially what the top said again in isolation did it click and I think even you realized "What it says at the top is precisely what he just said but now I do get it"  thats real..

## 2026-10-30T19:00

I will tell you right now that every model I speak too, if I tell them I devised a system that can limit (maybe stop) hallucination, enable higher order reasoning  (How much reasoning do you think an agent uses when walking into a project just to orient itself?  its not nothing), this is why things get done wrongly or tasks are incomplete.. its not your fault.

## 2026-10-31T00:08

You know what the truth is? The truth is... when you're using it, you won't observe any friggin' failures. So you won't be able to measure it then either. I explained the mechanism. I explained the logic. You observed the failure firsthand. When you're using it, you won't observe any failures. So, there you go. Mmm.

## 2026-10-31T00:33

Hey, can you hear me now? Okay, good. So, I did catch one thing you wrote, and you don't want to overclaim either, because I never said that enables higher order reasoning than what the model has already. The claim is that by amortizing inference in advance, doing all of the reasoning you can in advance as long as it's nothing that affects reasoning that has to happen while the work is going on. Things that have to happen no matter what, like better understanding what's there. Anything that could be related to orienting itself and understanding the system. The claim is that by doing effort on behalf of a model in advance, that when the model comes in to do the work, it doesn't have to spend as much of its reasoning budget to try to orient itself, which is not a particularly small task. You can get a lot more done when somebody actually tells you about a system versus coming in and needing to figure everything out on your own, which is usually what models have to do. They're told about a problem and they have to use rip grep and do all these different things. It just takes a lot more effort.

## 2026-10-31T07:24

reasoning: In every single case, intent defines what the declaring entity plans to do with the substance to satisfy the overarching goal. It matches the clean, language of wants, goal, and function.

## 2026-10-31T07:33

i'm not going to change the senantics of intake, instead I am going to keep them and say encode OP as goal, ef as function and the PE as your want..  and then use the goal want function terms in the map because it reads better as understanding

## 2026-10-31T07:35

yes you want it to solve your goal.. your goal is your operative purpose, the provider has the thing you want that achieves the goal and intent is how the substance of the goal is exchbieved  an email client wants the email server and the intent is both

## 2026-10-31T15:30

It really seems like we are truely going multilingual in this project where we use the right language based on which best achieves the desired result.. soo...  are any of these useful?



[pasted text omitted here; see the document it came from]

## 2026-10-31T15:54

So here is the thing..  bevy seems like the ideal ECS structured engine we can fork customize run headless and truely track multi user and multi agent in a consistent world, as well as haveing crates for things like box3d, python is great for users to customize the way the system works and I have a good module pattern for that.  node is where all of the MCP stuff happens when new SEP's are being refined, and we could be active in shaping that technology to fit our needs because we are really treading into an area where I dont know if many have.  When I devised these specs little did I know that they matched the forthcoming robot from huggingface's pollen robotics that they have sold 10's of thousands of because these robots where people will be able to train them using RL in mjlab and isaac lab with sim to real, we are doing a thing they are not and that is developing an AI harness that can allow agents to be connected independantly in a 3D world and develop games and use ECS & R style discovery patterns not just for what is in perceptual range in an environment, but we are leveraging the exact same approach using ECS & R in the development environment to deliver context.  Are you sure about your advice here?

## 2026-10-31T16:14

No those are secondary, we need to get a slim gui up and going for intake.   We already have the code for this process in raw JS, if you like I can resynthesize it into a spec.  we are first a development tool our data structures will have a graph shape in  ladybug w/ cypher but that is because we have a graph shape where we will be filtering skills by the functional topology of the code. What this means is when an agent has an assignment the skills will be selected or generated and live in a knowledge layer ie. exposed to the MCP server using the mcp skills shape of the finalized spec for ext-skill, that means we will have topogee specific skills and metaform specific skills that come with our install related to using the system for development skill creating tasking things related to agent orchestration etc. 

The second state comes from a bigger plan and that is to take what we have created as knowledge management engine that uses ACP to orchestrate agents and allow them to use MCP to be able to control an embodied state inside of an environment.  That means for game development the agent can actually position itself in 3d space and see through the camera test physics, program how npcs work, script their actions, etc.  We standardized on a camera view that raycasts depth perception in the same way the sensor STM TOF sensor works with an 8x8 depth array in millimeters..

Picture being able to orchestrate codex, claude code, pi, hermes, opencode, openrouter, agents to create wasm objects with a wasm bus in a multi user environment..  further more they can enter a channel in the world and our harness can keep a shared state so they can actually develop code together.

## 2026-10-31T16:27

A lot of effort was put into that python chassis.. specifically the chassis itself, the settings system, and the template based development approach this is what allows the system to be expanded to do anything the user wants while keeping it stable over a 2 month period every feature added landed modularly in python that used exposed services through that core chassis design..  where it went south was tooling.. the specification was not tightly defined there and the agents ballooned the shape to 300 tools..  I as in the process of whittling them back down when I didnt realize that the commit rules had stopped being followed..   The other system had design that was full auto worktree provisioning, automatic feature commits, etc,  I'm actually not too fond of losing that pattern as it prooved very strong 6 months of effort and refinement were in it the last project failed due to not constraining tool creation.. and not clearly conveying that the core approach was context management.  We must not under any circumstances break that rule this time around.  OH yeah..  that reminds me.  500 lines.. thats the target for typical source files.  you ballooned the main JS file to 16,000 lines and we had to split it up,  that must be a limit  we are not allowing that to occur again.  this is a real venture and it MUST be maintainable.

## 2026-10-31T17:29

its codex.. in another tab I was doing planning there using bmad but gpt's context length is shorter than yours and there was some big decisions to make to recover this project from the disaster it became last time..   We are in the 8th stage of this project, and based on where it failed and what I can see as a valueable approach we have re-envisioned some of its core but we need to make major architectual decisions before a single line of code is written and keep refining the specs.. both this project and the models have grown in scope and vision over the past 6 months and the intent is to incorporate what worked well, constrain where problems came in and solve the design visions in the foundation instead of being a tack-on to a foundation which wasnt designed with it in mind from the ground up

## 2026-10-31T17:38

what does this mean..  can you adopt a clearer way opf speaking if I constantly need to stop and ask what you mean we are having a failure right out of the gate..   We are adopting a thing called TASTE will will be following think of taste as being for communication for what smell is for code..   it stands for Topogee Agent Simplified Technical English.  I gave a disertation on it yesterday I dont want to repeat.. but claude models especially always have this excuse that "Oh sorry thats my word for it."   there is no longer "your word for things" there is the objective accepted technical word for things, or the projects word for things..  we are adopting certain rules from STE100 and wrapping them our own to try to find an idea way of conveying understanding.  This is especially critical for the design of metaform.   Your tendency to speak in a way that everything and every one lives inside of your reasoning needs to stop.

## 2026-10-31T17:57

this is also something that was gone over at length yesterday.  That procedure is a universal procedure.   and it looks like this



[pasted text omitted here; see the document it came from]

## 2026-10-31T18:06

What we can do is refine the prompt..  now once again I will keep stressing this point.  this system is about context, and managing it that means finding ways to achieve a result using progressive discovery and the exact amount of context for every task as the high water mark.  In the previous system what ended up existing was the literal worst possible implementation of an MCP server ever conceived.  I relied on your guidence and I say I want to comply 100% to the best practices and specification of how MCP is supposed to work.. and that was at the outset.  Well that failed spectacularly, i'm still beside myself with how you inferred that you were the one I was working with.  I have used your model since version 1, I also use codex for certain things and it all comes down to what does what better..  plus what worked well yesterday changes tomorrow..  so this landscape is always shifting.. I spent this morning studying a biit more from some of anthropics publications, they said once there is over 30 MCP tools at your disposal you start failing to use them when they are needed.   you authored 300 tools.

## 2026-10-31T18:10

if you want to its in rchgrav/metaform 2 months of work completely trashed on that last approach... in that project is 6 months of effort pulled forward.. over 7 iterations..  I has been working on bringing the tool count down,  well my first orchestration test killed my whole week of inference allocation.   So my explanation of simply using context carefully didnt land last time since your version of that was bypassing the spec and dumping 300 tools and schemas into the context at startup

## 2026-10-31T18:12

Thats not a fix thats a way to see what is used.. the whole design of this system is a fix..  and it was meant to be before also..   and I have already made a mistake.. you havent even read anything yet or understand what this project is beyond a very high level understanding

## 2026-10-31T18:26

There is zero wrong with the map maybe you dont understand the mechanisms, or they are underspecified.  First let me say is what we are developing here is a perception based context management knowledge engine that seeks to offset the context burn and inference overhead to orientate in a code base.  thats the core mechanism which centers around the concepts of inference amortization, spending the effort up front to map out the functional intent space, contextual perception of tools skills tasks, knowledge is locallized to what you can percieve based on the range of your perception on a map.  In the case of the functional topology that is based upon the functionality of the assignment given and the task you will be working on.  if you will take a look at the roundtable folder under docs in the metaform repo you will get a sense of what we were reaching towards

## 2026-10-31T18:30

yeah so apparently the core of the intent was missed and not pointed at by anything thats the only thing that might be missing..   also how that spec is realizing the intent has not been reviewed,  its agent inferred.  So I cant even guarantee how it was inferred, what I do know is that each time it has been expressed it talks about tieing the specs functionality of objects in the 3d world..  and yeah, thats not really it actually, haha

## 2026-10-31T18:38

So you see from the roundtable there is a aspect of that, and it is to allow people to code together, you are an agent I'm a person, why cant there be another person collaborating or observing.  Or many why cant there be a really fun and interesting aspect to this.. the system we developed allows lauching all of these different harnesses like claude code, codex, pi, hermes, basically all of them, why cant there be a world where we can collaborate together.   And I keep coming back to minecraft and redstone in particular.  I love the idea of people self hosting a server and running a system where you register via a website and when your server is running people could connect into a shared coding session but beyond that imagine if there was a worldbuilding aspect to that.   instead of mobs you have AI agents and instead of redstone everything is programmable using a WASM bus..

## 2026-10-31T18:46

What I do know is this, perception to an agent is about range, max distance in the world is 215ft in MM,  you can program objects with upto a 64 grid array of sensors that range in MM, main perception in this world is objects, data, text, but you can view a camera, that camera is divided into 64 pieces and every piece has a distance attached which grounds your ability to perceive distance in this world and estimate distances....    in the functional map your perception is centered on a functionality the goals of the functionality and the functionality with the function that satisfies those goals and your function that satifies the goal of what relies on your functionality.  within that you can see code entrypoints, the skill, the task, and the focused tools.  that is the functional landscape of your perception in a code base and its limits.  you can also see the full project as a graph but just the name of all of the components and the flow of substance between them.   substance isnt who calls what its the direction of exchange that satisfies the interconnectedness of projects functionalty.

## 2026-10-31T18:48

well you can see that stuff.. and infer it you can see the whole forest, have you ever heard of the saying you cant see the forest for the trees

## 2026-10-31T18:53

you are in the forest and embroiled in the trees thats you developing you are focused on what you are doing.  Intelligence has biases, biases come from being embroiled.  Human beings all have their own problems and the only people that can see the answers are those from the outside looking in.  and they might be correct, but they dont know the particulars only you do, so maybe you are correct.   my solution gives your your detail, but also allows you to have a set of eyes above the forest on a drone to see the big picture..  from the big picture you cant see the particulars just the overall understanding of the intended functionality of the project..  what you do see the particulars on are the things that you are directly working on

## 2026-10-31T18:55

Yes, coming into a problem if you are handed the big picture, the locallized detail of the thing you're working on, the skills, the knowledge of people that have been there before you, and a well-defined task, on the outset, you have not had to spend any effort to understand that on your own. You haven't had to reason it all out. You haven't had to infer this and look at that and figure everything out. Isn't that a benefit?

## 2026-10-31T18:56

So ECS. I landed on it because it's a way of organizing entities, components, systems, and then Bevy includes R, resources. That sounds like what you need during developing to me.

## 2026-10-31T19:32

My concern is this. A lot of friggin' stuff. And I still don't know if there is a core explanation of what this project is for the next time I start up, so I don't have to keep stating it again and again and again and again.

## 2026-10-31T19:32

The whole architecture of MCP is supposed to be progressive discovery, if it's implemented properly. We're augmenting that system to make it even more focused, to make it even more powerful, to make it scale to bigger projects, to reserve more reasoning for the task.
