UNWIND $item_keys AS selected_key
MATCH (item:ContextItem {key: selected_key})
RETURN item.key AS item_key, item.stable_id AS item_id,
       item.revision AS revision, item.kind AS kind,
       item.payload_mode AS payload_mode, item.payload_json AS payload_json,
       item.payload_uri AS payload_uri, item.native_schema_uri AS native_schema_uri,
       item.content_digest AS content_digest, item.byte_length AS byte_length;
