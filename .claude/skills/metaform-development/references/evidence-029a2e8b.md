user: "10 memories; 5 unread, including 5 updated. Read applicable unread contents with metaform memory read_unread node=element:code.dispatcher.agent."
assistant: "Same notice, nothing new."
assistant (tool call): mcp__metaform__memory_read_unread {"node":"element:code.dispatcher.agent","view":"full","must_contain":"work_over"} -> {"entities":[],"relations":[]}
assistant (tool call): mcp__metaform__memory_read_unread {"node":"element:code.dispatcher.agent","view":"full","must_contain":"autoticket"} -> {"entities":[],"relations":[]}
user: "5 memories; 5 unread, including 0 updated. Read applicable unread contents with metaform memory read_unread node=element:code.router.assignment."
assistant: "Same notice as before. I've already read those memories at code.router.assignment, and none of them touch ticket #9."