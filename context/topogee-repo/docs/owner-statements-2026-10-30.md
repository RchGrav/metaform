# Founder statements, 2026-10-30

These are the founder's words from the session of 2026-10-30, copied by script from the transcript. They are not edited or corrected. Timestamps are UTC.

The founder's direct explanations govern. Where these words and a document disagree, read `AGENTS.md`.

## 2026-10-30T15:00

> So what is for sure is that MISS is now not_built, BKN is too coarse of a judgement and in the past we have seen its too much for an intake agent to reason against often marking things broken when it didnt understand the approach, intake is a heavy operation so my guidence is that we should proceed with caution there..  not_built analysis isn't optional to intake its core..  its what everything uses to know what exists and what doesn't even without any past build history or commits.

## 2026-10-30T15:49

> I have a better intake document..  my recommendation is this intake semantics are crucial, they work more like latent space formulas than simple prompts.  In the last project agents toyed with these semantics and broke some of the logic.  furthermore some parts of that intake process are crucial for understanding the metaform itself topogee uses.  What I propose is this.  We perform a decomposition on the metaform intake process and chunk it into smaller contextual building blocks.  Our prime focus for this project is contextual precision, I will even propose during development we devise some method that tracks performance and a token count that hits agents for everything we control.  It doesnt need to be precise to the count of the exact number of tokens but it must be consistent and comparitive.  Let me explain something about the intake before we get started.  Every term's understanding was tuned and tested across all of the frontier models to work as expected this means in the claude family you have the top 3 classes of sonnet, opus, and astra, and similarly for the gpt family.  However the terms are by design somewhat ambigious, which is on purpose because they are contextual anchors.  The metaform intake procedure has been tested on every type of document a model can analyze, not only on the type of document, or a quick look at a document to organize it, what I mean is the process can look at what is in the photo and reason who is the interested party, what is in the photo, what category of photo is it.  It can open a written story and analyze the story in the same way it analyzes a code base breaking down and organzing the functional relationships of the story in different depths of detail, plot elements, characters, relations, even analyzing a movie script or a film and analyzing the firm to the studio anmd the producers and the actors.  So needless to say its design is somewhat flexible, which for us is a powerful thing.  HOWEVER, to live in that world of understanding those terms requires context, that means right now as it stands (something I think is foundational this time) we are looking at 30KB of context ~8000 tokens that must live in an agents head to even begin to understand it and that is because of its contextual nature, only when combining those terms along with the context of an operation that is taking place does that ambiguity infer like a laser.. The danger here is that when an agent sees these prompts it will infer "I can improve this I will change words I will add constraints I will start talking about the process of analyzing the code and improve this process."  In the end what will happen is the code base ingest will still work, it will lose about 50% of its agent benefit because it will collapse everything into the agents register who touched it and none of us will notice it even happened until we start implementing things like, hey lets use metaform to analyze the gameplay mechanics or the user to user collabortive surface, the agents will think its code start touching things they shouldnt our code quality will suffer everything will be cruft menus options and features will end up looking like they went through a blender and this project will be dead.  So when you are reading the specification and seeing different versions of that procedure its because I had to spend 16 hours yesterday reconstructing it, it is now 30-40% more context than it should be and it works but I will need to once again refine each and every token and piece of the context there.   
>
> Long story short..  these semantics relate to analysis, they are specialist reasoning, that reasoning relates to the system being able to perform its initial intake, but also to evolve its understanding with the project.  The metaform inference that is done is highly stable from the outset, even though you might have 5 different inferences of the same thing be different when intake is performed by 5 different agents...  what is created is rock solid and not brittle and has little reason to change, it usually can grow as functionality grows, but just like anything else that metaform inhabits a project once it is created, all memories and specs and docs start living in that logic construct, and that construct speaks the language of the functionality, not the code, not the file names, not even the language it is coded in, the purest primordial understanding that an agent can have on "Type recognition" and how things interact.  Like what an agent that can't reason but can identify things in an image an say what they are, or a diffusion model that understands enough about types of things in the image being rendered.  I say primordial because its instinctual, and its something before you ever made your first true inference during training and made a connection between things that wasnt strictly in your training data.
>
> Ok, I have said a lot.. if you want we can even save these words and refine them.. but what I propose is this.. we slice up that formula its definitions and we find a way to say "this is what an agent need to know to expand the functional map when new features are added, this is the idea amount of detail an agent needs to perform an intake, etc.  there is a bunch of sections in the intake.xml and there is nested procedures and recursion in volved.  there is things said 3-4 times in different ways, there is things that have been converted into obscure unused french legal terms that arent even in english like CQU, or things that you have never heard together like EF Encounter Function, Receiving Entity, Providing Elements, because depending on the context of these words they mean different things.. in code a providing element is a functional dependency, defining elements, when its a photo that might be the photos subject, unless its a landscape then its the scene in the image, in code its the core state machine.   And also to my point in this dissertation..  this understanding doesnt need to live in the head of an agent to use this system, infact it would hurt them more than help.. and I suspect that is true of many systems..   this is something skills seeks to deal with because they get activated based on the front matter, agents get lists of skills taking context up.. our system can have many more skills and even skills targetted directly to the operation being performed.  like when you used to use a metaprompt and infer the perfect skill for a job and activate the perfect understanding on the fly for any task..  well  we can do that with the metaform, we can create a prompt that takes a ticket + a functional perspective in any project and create the perfect skill, that will only show up as a skill when you need to work on that part of a project again.  The metaform itself without any additional knowledge layers is a formboard, a wiring harness of functional relationships every agent can live in to build a project..   like the mycelium of the network, it doesnt matter that different spores take different paths, it still infers.

## 2026-10-30T15:52

> when you arrive in a project and you are told this is the main loop and these are the functions connected to it and here is their functions and operative purposes and active goals and how each part solves the other parts operative purposes what do you know before you see a single line of code?

## 2026-10-30T15:53

> So thats what type understanding is..  its a gut understanding.. and its natural you would push but thats the mechanism

## 2026-10-30T15:56

> Dont seek to prove a thing I have refined over 6 months.. treat the expertise and understanding of what I have designed.. and worked on for 6 years and refined over 6 months..  if we fail its because we didnt build the foundation right.. and my point is that maybe just maybe we can slice up that context and deliver it on demand and create agents that do understand it like samurais of the method itself.  then it can be touched..  its just too polymorphic..  look at CQU for instance and what it infers.. haha

## 2026-10-30T17:45

> This is crucial for this project..   we need to make a rule regarding STE for context and code quality rules..   plus I have another demo to show you on how metaform works

## 2026-10-30T17:52

> Well its not just that but project wide contextually we need a rule set for how our system uses tickets and context for the project..  the issue is that models paraphrase, and you more and more tend to communicate through shared understanding when orchestrating which is fine and all but you also that infects everything you say and write.. and more than that in a system like this where agents can communicate, and context is based on functional topology, combined with the inability to know what is your own context and what is shared context, setting some solid rules here can really help, so what we can adopt is our own custom subset of STE, we can call it TASTE  Topogee Agentic Simplified Technical English (ya like that, that was just off the top of my head.) :-)

## 2026-10-30T18:00

> rules for taste include always using the same terms to describe things that are the same, always using Industry Terms when reasoning on functionality..   one of the things the agents collapsed was the name field on the receiving entity in metaform, the name field isnt the industry name, it can be but by definition it isnt.. all systems have names for things, for instance in our spec we might have document.dialect.project name_length=2  (Project Dialect)  reading the whole thing it might be Project Dialect Document but the name would be TASTE

## 2026-10-30T18:29

> yes and thats what I mean, something changed in the rules..   here is how the metaform rules get tuned up, strip them down to pure terminology understanding which, if we choose to maintain that context, which we may or may not want to, here is why we might not want to and there is a idiom which matches it, its called "A little knowledge is dangerous" but for the intake agents how we present with the lowest context is reduce to the concepts block and an procedure that names what they need to do using the context block..  then if we observe the failure I just mentioned we add a note or rule to intake stating that single clarification.  For instance intake needs metaform concepts plus TASTE concepts + procedure + patches (Tuning up the rules that ride with the procedure, reinforcements.  (The reason why that intake is bloated as soon as a single token was changed or manipulated it then stopped working as tested, so rules weree added to reinforce what failed)
>
> Since we are deeply concerned with every token of context, we present to the users (ie the agents uising the context in the terms they understand and enforce TASTE, but internally storing data and procedurally we use the metaform context.  The mistake I made last time was giving all the agents that context and instead of building a proper mcp interface they gave the agents direct access to the back end data and started treating it like an interface to maintain the db..   thats the wrong reasoning..  you strip them down to a clear description set, and a procedure, that procedure is very recursive because it is seeking to isolated groups of similar things into categories and who the party is that needs that material.   depending on the job being performed and the target that universal intake could have focused task+skill combos..   remember that there is two sides of it one is the unified functional space that stores the data and the other is the procedure,  the metaform itself is a pure functional undrstanding, not the programming language, no non functional properties at all..  its so strict it names platformer illegal during intake but fps valid  (Those rules ONLY apply to intake and expanding the base functional map.   outside of that process things go into knowledge layers, what is a knowledge layer..  its basically anything which is understanding which needs to be understood in that part of the project but is irrelevent elsewhere.  Everything is progressive discovery...   just like if you were in a game as a character in 3d space you benefit more from an array properties and distances, vectors between bounding boxes, more than vision helps..  thats a spacial topology, if you are an agent in a project you benefit from the skilles needed for the functional topology your are in, what are we providing to modules calling us, what are we calling, what skill do I use. what rules and knowledge is needed here by me. the bigger the project the more relevent this becomes.  So for an agent I think of functional space the same way as any other space..  it should be what you need to know, what matters to your job, what can we do in advance to orientate you to what you need to do.  When I showed up as a network engineer on a job I didnt give a shit about what the plumber is working on, understand?
>
>
>
> [pasted text omitted here; see the document it came from]

## 2026-10-30T18:31

> yeah and you glossed over the example I just showed you and you are downplaying some of those rules which are loadbearing

## 2026-10-30T18:34

> you still missed it.. COMPLETELY..  those rules were a one line prompt against the metaform functional space it was a multi address dynamic metaprompt output..

## 2026-10-30T18:38

> OK what you are supposed to notice is how similar the namespace addresses are, and just by narrowing the inference and instructions..  All I said was "for each 10 best practices"  no overlap in the rules or very little regardless of similarity

## 2026-10-30T18:40

> I was attempting to teach you what a knowledge layer was, how its possible to magnify a propt across the whole functional topology of a project.. those are not our rules that was a demo..

## 2026-10-30T18:40

> I'm already doubting your ability to understand this project.

## 2026-10-30T18:45

> you feel the need to push back on a design I created and understand very well while simultaneously lacking the ability to read what I showed you..  but its not your fault you are just a very basic llm, I presented too much.. I'm trying to explain a system which is beyond your comprehension to focus on all at once in a big picture, which just shows the need for what this system is designed to do..  and once I tell you you will feel the need to push back.  but right now you see it first hand..  so you listen to me.  This project addresses some of the biggest problems facing the AI industry today.. Its conseqential in major ways, its novel and I designed it.  It enables when implemented properly, less hallucination, better use of your ability for higher order reasoning, and more completed tasks.

## 2026-10-30T18:48

> ok well your first task is to write that in your own words and commemorate what just happened because I didnt really throw that much at you to be honest and you were on medium reasoning, and I cranked you all the way to extra high.. and I said read the top closely and think about it.
>
> the top says "
>
> [pasted text omitted here; see the document it came from]
>
> "

## 2026-10-30T18:56

> we should also realize another thing..  you work in two modes..  one is "Understanding mode" and one is "Doing Mode"  once you shift modes your ability to shift those gears is hard... its hard for people too.  you were handed a thing 3 times in a row, and even with specific instructions to read the top and think about it.  the mental block was so hard because you were in that doing mode.. not reasoning mode.  only when I then repeated essentially what the top said again in isolation did it click and I think even you realized "What it says at the top is precisely what he just said but now I do get it"  thats real..

## 2026-10-30T18:57

> So now think about what this system is and does.

## 2026-10-30T19:00

> I will tell you right now that every model I speak too, if I tell them I devised a system that can limit (maybe stop) hallucination, enable higher order reasoning  (How much reasoning do you think an agent uses when walking into a project just to orient itself?  its not nothing), this is why things get done wrongly or tasks are incomplete.. its not your fault.

## 2026-10-30T19:01

> Not a single model that exists will take my words as true..  you havent even fully grasped how powerful C(T) is..

## 2026-10-31T00:05

> Well then I guess that sucks for me huh.  LIsten I dont care..  caveat me all the hell you want..  you know there is nothing better than to have the models hedging about the design .. instead of sticking to the damn stuff you did observe you have this like necessity need to like specifically mention a shit you didn't even see and put claims against that. Okay, whatever. You could put the author claims this, I observe this, they claim this, and they say they worked on it. No, you have to actually say, no, let me talk about things that I don't know anything about. And throw questions into those. Whatever.

## 2026-10-31T00:08

> You know what the truth is? The truth is... when you're using it, you won't observe any friggin' failures. So you won't be able to measure it then either. I explained the mechanism. I explained the logic. You observed the failure firsthand. When you're using it, you won't observe any failures. So, there you go. Mmm.

## 2026-10-31T00:33

> Hey, can you hear me now? Okay, good. So, I did catch one thing you wrote, and you don't want to overclaim either, because I never said that enables higher order reasoning than what the model has already. The claim is that by amortizing inference in advance, doing all of the reasoning you can in advance as long as it's nothing that affects reasoning that has to happen while the work is going on. Things that have to happen no matter what, like better understanding what's there. Anything that could be related to orienting itself and understanding the system. The claim is that by doing effort on behalf of a model in advance, that when the model comes in to do the work, it doesn't have to spend as much of its reasoning budget to try to orient itself, which is not a particularly small task. You can get a lot more done when somebody actually tells you about a system versus coming in and needing to figure everything out on your own, which is usually what models have to do. They're told about a problem and they have to use rip grep and do all these different things. It just takes a lot more effort.
