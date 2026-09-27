"""The SQL of one metaform's store, STORE-003 to STORE-040, at schema version 2.

Every table follows STORE-004: one row per thing, and no row holds a collection.
`address_elements` remembers the element id of every address the store has held,
so an element recorded again at its address is the same element, STORE-009.
Two indexes are added beyond the section's own: `elements_by_address`, for the
history of one address, STORE-005, and `findings_by_layer`, which lets
discarding a layer remove its findings rows without a scan, STORE-042 and
STORE-032.
"""
from __future__ import annotations

STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS element_ids(element_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS join_ids(
  join_id  TEXT PRIMARY KEY,
  receiver TEXT NOT NULL REFERENCES element_ids(element_id)
);
CREATE TABLE IF NOT EXISTS subtype_ids(
  subtype_id TEXT PRIMARY KEY,
  join_id    TEXT NOT NULL REFERENCES join_ids(join_id)
);
CREATE TABLE IF NOT EXISTS identities(
  id   TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('element','join','subtype','item'))
);

CREATE TABLE IF NOT EXISTS types(
  address TEXT PRIMARY KEY,
  parent  TEXT REFERENCES types(address)
);
CREATE INDEX IF NOT EXISTS types_by_parent ON types(parent);

CREATE TABLE IF NOT EXISTS layers(
  layer_id    TEXT PRIMARY KEY,
  metaform_id TEXT NOT NULL,
  name        TEXT NOT NULL UNIQUE,
  module      TEXT NOT NULL,
  variable    TEXT NOT NULL,
  mutable     INTEGER NOT NULL CHECK(mutable IN (0, 1)),
  hideable    INTEGER NOT NULL CHECK(hideable IN (0, 1)),
  result_id   TEXT,
  kind        TEXT NOT NULL DEFAULT 'layer' CHECK(kind IN ('layer','intake','memory','correction')),
  created     TEXT NOT NULL,
  ready       TEXT
);
CREATE INDEX IF NOT EXISTS layers_by_kind ON layers(kind, ready);
CREATE TABLE IF NOT EXISTS hidden_layers(layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id));
CREATE TABLE IF NOT EXISTS layer_fields(
  layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  position INTEGER NOT NULL,
  name     TEXT NOT NULL,
  PRIMARY KEY(layer_id, position)
);
CREATE TABLE IF NOT EXISTS layer_tags(
  layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  tag      TEXT NOT NULL CHECK(length(tag) BETWEEN 1 AND 64),
  PRIMARY KEY(layer_id, tag)
);
CREATE INDEX IF NOT EXISTS layer_tags_by_tag ON layer_tags(tag, layer_id);
CREATE TABLE IF NOT EXISTS layer_sources(
  layer_id        TEXT NOT NULL REFERENCES layers(layer_id),
  source_layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  PRIMARY KEY(layer_id, source_layer_id)
);
CREATE INDEX IF NOT EXISTS layer_sources_by_source ON layer_sources(source_layer_id);
CREATE TABLE IF NOT EXISTS reexamine(
  layer_id            TEXT NOT NULL REFERENCES layers(layer_id),
  correction_layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  thing_id            TEXT NOT NULL,
  PRIMARY KEY(layer_id, correction_layer_id, thing_id)
);
CREATE TABLE IF NOT EXISTS provenance(
  layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id),
  module   TEXT NOT NULL,
  workflow TEXT,
  prompt   TEXT,
  model    TEXT,
  role     TEXT,
  blinded  INTEGER CHECK(blinded IN (0, 1))
);
CREATE TABLE IF NOT EXISTS correction_stack(
  position INTEGER PRIMARY KEY,
  layer_id TEXT NOT NULL UNIQUE REFERENCES layers(layer_id)
);

CREATE TABLE IF NOT EXISTS elements(
  row        INTEGER PRIMARY KEY,
  element_id TEXT NOT NULL REFERENCES element_ids(element_id),
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  address    TEXT NOT NULL REFERENCES types(address),
  extra      TEXT,
  op         TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason     TEXT,
  evidence   TEXT,
  UNIQUE(element_id, layer_id)
);
CREATE TABLE IF NOT EXISTS current_elements(
  element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
  row        INTEGER NOT NULL UNIQUE REFERENCES elements(row),
  address    TEXT NOT NULL UNIQUE,
  moved      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS address_elements(
  address    TEXT PRIMARY KEY REFERENCES types(address),
  element_id TEXT NOT NULL REFERENCES element_ids(element_id)
);
CREATE INDEX IF NOT EXISTS elements_by_layer ON elements(layer_id);
CREATE INDEX IF NOT EXISTS elements_by_address ON elements(address);

CREATE TABLE IF NOT EXISTS joins(
  row         INTEGER PRIMARY KEY,
  join_id     TEXT NOT NULL REFERENCES join_ids(join_id),
  layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
  type        TEXT NOT NULL DEFAULT 'purpose',
  receiver    TEXT NOT NULL REFERENCES element_ids(element_id),
  provider    TEXT NOT NULL REFERENCES element_ids(element_id),
  purpose     TEXT,
  function    TEXT,
  ef          TEXT CHECK(ef IN ('Function','Encounter')),
  relation    TEXT,
  verb        TEXT,
  observation TEXT,
  non_goal    TEXT,
  extra       TEXT,
  stack_at    INTEGER NOT NULL DEFAULT 0,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT,
  UNIQUE(join_id, layer_id)
);
CREATE TABLE IF NOT EXISTS current_joins(
  join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
  row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
  receiver TEXT NOT NULL,
  provider TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_joins_by_receiver ON current_joins(receiver);
CREATE INDEX IF NOT EXISTS current_joins_by_provider ON current_joins(provider);
CREATE INDEX IF NOT EXISTS joins_by_layer ON joins(layer_id);

CREATE TABLE IF NOT EXISTS subtypes(
  row         INTEGER PRIMARY KEY,
  subtype_id  TEXT NOT NULL REFERENCES subtype_ids(subtype_id),
  layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
  address     TEXT NOT NULL REFERENCES types(address),
  name        TEXT,
  name_length INTEGER,
  role        TEXT CHECK(role IN ('DE','SE','NE')),
  function    TEXT,
  ef          TEXT CHECK(ef IN ('Function','Encounter')),
  relation    TEXT,
  verb        TEXT,
  observation TEXT,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT,
  UNIQUE(subtype_id, layer_id)
);
CREATE TABLE IF NOT EXISTS current_subtypes(
  subtype_id TEXT PRIMARY KEY REFERENCES subtype_ids(subtype_id),
  row        INTEGER NOT NULL UNIQUE REFERENCES subtypes(row),
  join_id    TEXT NOT NULL,
  address    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_subtypes_by_join ON current_subtypes(join_id);
CREATE INDEX IF NOT EXISTS current_subtypes_by_address ON current_subtypes(address);
CREATE INDEX IF NOT EXISTS subtypes_by_layer ON subtypes(layer_id);

CREATE TABLE IF NOT EXISTS refs(
  ref_id    INTEGER PRIMARY KEY,
  owner     TEXT NOT NULL CHECK(owner IN ('element','join','subtype','item','property')),
  owner_row INTEGER NOT NULL,
  position  INTEGER NOT NULL,
  key       TEXT NOT NULL,
  value     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS refs_by_owner ON refs(owner, owner_row, position);
CREATE INDEX IF NOT EXISTS refs_by_key_value ON refs(key, value);

CREATE TABLE IF NOT EXISTS item_ids(
  item_id  TEXT PRIMARY KEY,
  layer_id TEXT NOT NULL REFERENCES layers(layer_id)
);
CREATE TABLE IF NOT EXISTS items(
  row         INTEGER PRIMARY KEY,
  item_id     TEXT NOT NULL REFERENCES item_ids(item_id),
  layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
  target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join','subtype')),
  target_id   TEXT NOT NULL,
  value       TEXT NOT NULL,
  link_kind   TEXT CHECK(link_kind IN ('element','join','subtype')),
  link_id     TEXT,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT,
  UNIQUE(item_id, layer_id)
);
CREATE TABLE IF NOT EXISTS current_items(
  item_id     TEXT PRIMARY KEY REFERENCES item_ids(item_id),
  row         INTEGER NOT NULL UNIQUE REFERENCES items(row),
  layer_id    TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  link_kind   TEXT,
  link_id     TEXT
);
CREATE INDEX IF NOT EXISTS current_items_by_layer ON current_items(layer_id, row);
CREATE INDEX IF NOT EXISTS current_items_by_target ON current_items(target_kind, target_id, layer_id);
CREATE INDEX IF NOT EXISTS current_items_by_link ON current_items(link_kind, link_id, layer_id);
CREATE INDEX IF NOT EXISTS items_by_layer ON items(layer_id);

CREATE VIRTUAL TABLE IF NOT EXISTS item_text USING fts5(value, content='items', content_rowid='row');
CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
  INSERT INTO item_text(rowid, value) VALUES (new.row, new.value);
END;
CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
  INSERT INTO item_text(item_text, rowid, value) VALUES ('delete', old.row, old.value);
END;
CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE OF value ON items BEGIN
  INSERT INTO item_text(item_text, rowid, value) VALUES ('delete', old.row, old.value);
  INSERT INTO item_text(rowid, value) VALUES (new.row, new.value);
END;

CREATE TABLE IF NOT EXISTS properties(
  row         INTEGER PRIMARY KEY,
  property_id TEXT NOT NULL,
  layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
  element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
  value       TEXT NOT NULL,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT,
  UNIQUE(property_id, layer_id)
);
CREATE TABLE IF NOT EXISTS current_properties(
  property_id TEXT PRIMARY KEY,
  row         INTEGER NOT NULL UNIQUE REFERENCES properties(row),
  layer_id    TEXT NOT NULL,
  element_id  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_properties_by_element ON current_properties(element_id, layer_id);
CREATE INDEX IF NOT EXISTS current_properties_by_layer ON current_properties(layer_id, element_id, property_id);
CREATE INDEX IF NOT EXISTS properties_by_layer ON properties(layer_id);

CREATE TABLE IF NOT EXISTS selections(
  address  TEXT NOT NULL REFERENCES types(address),
  layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  kind     TEXT NOT NULL CHECK(kind IN ('select','mask')),
  PRIMARY KEY(address, kind, layer_id)
);
CREATE INDEX IF NOT EXISTS selections_by_layer ON selections(layer_id);

CREATE TABLE IF NOT EXISTS challenge_states(
  item_id   TEXT PRIMARY KEY,
  state     TEXT NOT NULL CHECK(state IN ('A','B','C','plan')),
  link_kind TEXT CHECK(link_kind IN ('element','join')),
  link_id   TEXT,
  answered  TEXT NOT NULL,
  approved  TEXT
);
CREATE INDEX IF NOT EXISTS challenge_states_by_state ON challenge_states(state);
CREATE TABLE IF NOT EXISTS plans(
  element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
  join_id    TEXT REFERENCES join_ids(join_id),
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  source     TEXT NOT NULL CHECK(source IN ('direct','approved')),
  item_id    TEXT
);
CREATE INDEX IF NOT EXISTS plans_by_layer ON plans(layer_id);

CREATE TABLE IF NOT EXISTS unapplied(
  layer_id TEXT NOT NULL REFERENCES layers(layer_id),
  kind     TEXT NOT NULL CHECK(kind IN ('element','join','subtype','property','item')),
  thing_id TEXT NOT NULL,
  reason   TEXT NOT NULL,
  PRIMARY KEY(layer_id, kind, thing_id)
);

CREATE TABLE IF NOT EXISTS element_roles(
  element_id TEXT NOT NULL,
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  role       TEXT NOT NULL,
  PRIMARY KEY(element_id, layer_id)
);
CREATE INDEX IF NOT EXISTS element_roles_by_role ON element_roles(layer_id, role);
CREATE INDEX IF NOT EXISTS element_roles_by_layer ON element_roles(layer_id, element_id);

CREATE TABLE IF NOT EXISTS findings(
  row         INTEGER PRIMARY KEY,
  target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join','subtype')),
  target_id   TEXT NOT NULL,
  layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
  flag        TEXT NOT NULL CHECK(flag IN ('missing','broken','cruft')),
  note        TEXT,
  UNIQUE(target_kind, target_id, layer_id)
);
CREATE INDEX IF NOT EXISTS findings_by_flag ON findings(flag, row);
CREATE INDEX IF NOT EXISTS findings_by_target ON findings(target_kind, target_id);
CREATE INDEX IF NOT EXISTS findings_by_layer ON findings(layer_id);

CREATE TABLE IF NOT EXISTS reports(
  report_id TEXT PRIMARY KEY,
  run_id    TEXT NOT NULL,
  layer_id  TEXT REFERENCES layers(layer_id),
  kind      TEXT NOT NULL CHECK(kind IN ('report','feedback','shape')),
  created   TEXT NOT NULL,
  size      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_by_layer ON reports(layer_id, kind);
CREATE INDEX IF NOT EXISTS reports_by_time ON reports(created, report_id);
"""
