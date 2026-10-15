I noticed the fourth touch—a second write a second later—was marking the watch dirty even though nothing actually changed, since the start event matched the same identity and offset. I'll update the logic so it only marks dirty when the position actually moves.

Paperclip: its server serves /api/companies/{id}/events/ws, the live events WebSocket its own pages follow (server/src/realtime/live-events-ws.ts; activity.logged carries entityType and entityId, server/src/services/activity-log.ts).

uvicorn.Server.main_loop wakes 10x a second. twilio/server.py Serving and node/serving.py Serving override main_loop to await an exit Event, make should_exit a property whose setter wakes the loop (uvicorn's own handle_exit sets it), and set ready on startup.