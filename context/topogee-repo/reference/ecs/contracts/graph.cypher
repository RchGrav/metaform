CREATE NODE TABLE MapSnapshot(
  key STRING, project_id STRING, repository_id STRING, commit_oid STRING,
  manifest_digest STRING, parent_key STRING, created_at STRING, state STRING,
  PRIMARY KEY(key));
CREATE NODE TABLE Namespace(
  key STRING, snapshot_key STRING, address STRING, depth INT64,
  PRIMARY KEY(key));
CREATE NODE TABLE Element(
  key STRING, snapshot_key STRING, address STRING, name STRING,
  name_length INT64, role STRING, PRIMARY KEY(key));
CREATE NODE TABLE PurposeJoin(
  key STRING, snapshot_key STRING, stable_id STRING, purpose STRING,
  ef STRING, ifd STRING, PRIMARY KEY(key));
CREATE NODE TABLE IceBlock(
  key STRING, snapshot_key STRING, block_number STRING, explanation STRING,
  PRIMARY KEY(key));
CREATE NODE TABLE Layer(
  key STRING, snapshot_key STRING, stable_id STRING, name STRING,
  variable STRING, kind STRING, state STRING, mutable BOOL, hidden BOOL,
  PRIMARY KEY(key));
CREATE NODE TABLE ContextItem(
  key STRING, snapshot_key STRING, stable_id STRING, revision STRING,
  kind STRING, name STRING, summary STRING, content_role STRING,
  payload_mode STRING, payload_json STRING, payload_uri STRING,
  native_schema_uri STRING, content_digest STRING, byte_length INT64,
  objective_purpose STRING, PRIMARY KEY(key));
CREATE NODE TABLE RuntimeRecord(
  key STRING, project_id STRING, kind STRING, revision INT64,
  payload_json STRING, PRIMARY KEY(key));

CREATE REL TABLE IN_SNAPSHOT(
  FROM Namespace TO MapSnapshot, FROM Element TO MapSnapshot,
  FROM PurposeJoin TO MapSnapshot, FROM IceBlock TO MapSnapshot,
  FROM Layer TO MapSnapshot, FROM ContextItem TO MapSnapshot);
CREATE REL TABLE AT_ADDRESS(FROM Element TO Namespace);
CREATE REL TABLE PARENT(FROM Namespace TO Namespace);
CREATE REL TABLE ANCESTOR(FROM Namespace TO Namespace, hops INT64);
CREATE REL TABLE OWNS(FROM Element TO PurposeJoin);
CREATE REL TABLE PROVIDED_BY(FROM PurposeJoin TO Element);
CREATE REL TABLE CONTAINS(FROM Element TO Element);
CREATE REL TABLE MEMBER_OF(FROM Element TO IceBlock);
CREATE REL TABLE INCIDENT(FROM Namespace TO PurposeJoin, side STRING);
CREATE REL TABLE IN_LAYER(FROM ContextItem TO Layer);
CREATE REL TABLE DERIVED_FROM(FROM Layer TO Layer);
CREATE REL TABLE SPECIFIES(FROM ContextItem TO PurposeJoin);
CREATE REL TABLE SUPPORTS(FROM ContextItem TO ContextItem);
CREATE REL TABLE USES_TOOL(FROM ContextItem TO ContextItem);
CREATE REL TABLE DEPENDS_ON(FROM ContextItem TO ContextItem);
CREATE REL TABLE HAS_SKILL(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE OFFERS(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE HAS_TASK(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE HAS_SPEC(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE HAS_DOC(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE HAS_MEMORY(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
CREATE REL TABLE HAS_ITEM(
  FROM Namespace TO ContextItem, FROM PurposeJoin TO ContextItem,
  attachment_key STRING, scope STRING);
