MATCH (receiver:Element {key: $receiver_key})-[:OWNS]->(j:PurposeJoin)
MATCH (j)-[:PROVIDED_BY]->(provider:Element)
MATCH (spec:ContextItem)-[:SPECIFIES]->(j)
MATCH (skill:ContextItem)-[:SUPPORTS]->(spec)
MATCH (skill)-[:USES_TOOL]->(tool:ContextItem)
WHERE j.snapshot_key = receiver.snapshot_key
  AND provider.snapshot_key = receiver.snapshot_key
  AND spec.snapshot_key = receiver.snapshot_key
  AND skill.snapshot_key = receiver.snapshot_key
  AND tool.snapshot_key = receiver.snapshot_key
RETURN receiver.address AS receiver, j.stable_id AS join_id,
       j.purpose AS operative_purpose, j.ef AS encounter_function,
       provider.address AS provider, spec.stable_id AS specification_id,
       spec.objective_purpose AS objective_purpose,
       skill.stable_id AS skill_id, tool.stable_id AS tool_id;
