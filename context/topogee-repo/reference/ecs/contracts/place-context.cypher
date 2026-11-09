MATCH (leaf:Namespace {key: $leaf_key})-[lineage:ANCESTOR]->(at:Namespace)
MATCH (at)-[attachment]->(item:ContextItem)-[:IN_LAYER]->(layer:Layer)
WHERE item.snapshot_key = leaf.snapshot_key
  AND layer.snapshot_key = leaf.snapshot_key
  AND layer.state = 'finished'
  AND NOT (layer.key IN $excluded_layer_keys)
  AND (lineage.hops = 0 OR attachment.scope = 'descendants')
RETURN item.key AS item_key, item.stable_id AS item_id,
       item.revision AS revision, item.kind AS kind,
       item.name AS name, item.summary AS summary,
       item.content_role AS content_role,
       item.payload_mode AS payload_mode, item.payload_uri AS payload_uri,
       item.native_schema_uri AS native_schema_uri,
       item.content_digest AS content_digest, item.byte_length AS byte_length,
       at.address AS via_address, '' AS via_join,
       lineage.hops AS namespace_hops, 0 AS join_hops,
       attachment.attachment_key AS attachment_key, layer.key AS layer_key
UNION ALL
MATCH (leaf:Namespace {key: $leaf_key})-[lineage:ANCESTOR]->(at:Namespace)
MATCH (at)-[incidence:INCIDENT]->(j:PurposeJoin)
MATCH (j)-[attachment]->(item:ContextItem)-[:IN_LAYER]->(layer:Layer)
WHERE item.snapshot_key = leaf.snapshot_key
  AND j.snapshot_key = leaf.snapshot_key
  AND layer.snapshot_key = leaf.snapshot_key
  AND layer.state = 'finished'
  AND NOT (layer.key IN $excluded_layer_keys)
  AND (lineage.hops = 0 OR
       (incidence.side = 'receiver' AND attachment.scope = 'descendants'))
RETURN item.key AS item_key, item.stable_id AS item_id,
       item.revision AS revision, item.kind AS kind,
       item.name AS name, item.summary AS summary,
       item.content_role AS content_role,
       item.payload_mode AS payload_mode, item.payload_uri AS payload_uri,
       item.native_schema_uri AS native_schema_uri,
       item.content_digest AS content_digest, item.byte_length AS byte_length,
       at.address AS via_address, j.stable_id AS via_join,
       lineage.hops AS namespace_hops, 1 AS join_hops,
       attachment.attachment_key AS attachment_key, layer.key AS layer_key;
