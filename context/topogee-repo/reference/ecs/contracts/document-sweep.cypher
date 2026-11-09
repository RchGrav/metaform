MATCH (place:Namespace)-[attachment]->(item:ContextItem)-[:IN_LAYER]->(layer:Layer)
WHERE place.snapshot_key = $snapshot_key
  AND item.snapshot_key = $snapshot_key
  AND layer.snapshot_key = $snapshot_key
  AND item.kind IN ['specification', 'documentation']
  AND layer.state = 'finished'
  AND NOT (layer.key IN $excluded_layer_keys)
RETURN place.address AS address, '' AS join_id,
       attachment.attachment_key AS attachment_key,
       item.stable_id AS item_id, item.revision AS revision,
       item.kind AS kind, item.content_digest AS content_digest,
       item.payload_mode AS payload_mode, item.payload_json AS payload_json,
       item.payload_uri AS payload_uri, item.native_schema_uri AS native_schema_uri
UNION ALL
MATCH (receiver:Element)-[:OWNS]->(j:PurposeJoin)
MATCH (j)-[attachment]->(item:ContextItem)-[:IN_LAYER]->(layer:Layer)
WHERE receiver.snapshot_key = $snapshot_key
  AND j.snapshot_key = $snapshot_key
  AND item.snapshot_key = $snapshot_key
  AND layer.snapshot_key = $snapshot_key
  AND item.kind IN ['specification', 'documentation']
  AND layer.state = 'finished'
  AND NOT (layer.key IN $excluded_layer_keys)
RETURN receiver.address AS address, j.stable_id AS join_id,
       attachment.attachment_key AS attachment_key,
       item.stable_id AS item_id, item.revision AS revision,
       item.kind AS kind, item.content_digest AS content_digest,
       item.payload_mode AS payload_mode, item.payload_json AS payload_json,
       item.payload_uri AS payload_uri, item.native_schema_uri AS native_schema_uri;
