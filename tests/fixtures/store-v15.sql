CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS element_ids(element_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS join_ids(join_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS identities(
  id   TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('element','join','item'))
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
  kind        TEXT NOT NULL DEFAULT 'layer' CHECK(kind IN ('layer','intake','memory')),
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
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  changed_in TEXT NOT NULL REFERENCES layers(layer_id),
  thing_id   TEXT NOT NULL,
  PRIMARY KEY(layer_id, changed_in, thing_id)
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

CREATE TABLE IF NOT EXISTS elements(
  row        INTEGER PRIMARY KEY,
  element_id TEXT NOT NULL REFERENCES element_ids(element_id),
  layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
  address     TEXT NOT NULL REFERENCES types(address),
  name_length INTEGER,
  name        TEXT,
  role        TEXT,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT
);
CREATE INDEX IF NOT EXISTS elements_by_id ON elements(element_id, row);
CREATE TABLE IF NOT EXISTS current_elements(
  element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
  row        INTEGER NOT NULL UNIQUE REFERENCES elements(row),
  address    TEXT NOT NULL UNIQUE,
  role       TEXT
);
CREATE INDEX IF NOT EXISTS current_elements_by_role ON current_elements(role, element_id);
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
  type        TEXT NOT NULL DEFAULT 'require',
  parent      TEXT REFERENCES join_ids(join_id),
  receiver    TEXT REFERENCES element_ids(element_id),
  provider    TEXT NOT NULL REFERENCES element_ids(element_id),
  name        TEXT,
  purpose     TEXT,
  ef          TEXT,
  ifd         TEXT,
  verb        TEXT,
  non_goal    TEXT,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT
);
CREATE INDEX IF NOT EXISTS joins_by_id ON joins(join_id, row);
CREATE TABLE IF NOT EXISTS current_joins(
  join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
  row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
  receiver TEXT NOT NULL,
  provider TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_joins_by_receiver ON current_joins(receiver);
CREATE INDEX IF NOT EXISTS current_joins_by_provider ON current_joins(provider);
CREATE INDEX IF NOT EXISTS joins_by_layer ON joins(layer_id);

CREATE TABLE IF NOT EXISTS current_subtypes(
  join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
  row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
  parent   TEXT NOT NULL,
  provider TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS current_subtypes_by_parent ON current_subtypes(parent);
CREATE INDEX IF NOT EXISTS current_subtypes_by_provider ON current_subtypes(provider);

CREATE TABLE IF NOT EXISTS refs(
  ref_id    INTEGER PRIMARY KEY,
  owner     TEXT NOT NULL CHECK(owner IN ('element','join','item','property')),
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
  target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join')),
  target_id   TEXT NOT NULL,
  value       TEXT NOT NULL,
  link_kind   TEXT CHECK(link_kind IN ('element','join')),
  link_id     TEXT,
  extra       TEXT,
  op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),
  reason      TEXT,
  evidence    TEXT
);
CREATE INDEX IF NOT EXISTS items_by_id ON items(item_id, row);
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
  evidence    TEXT
);
CREATE INDEX IF NOT EXISTS properties_by_id ON properties(property_id, row);
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

CREATE TABLE IF NOT EXISTS work(
  row         INTEGER PRIMARY KEY,
  work_id     TEXT NOT NULL UNIQUE,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  condition   TEXT NOT NULL,
  note        TEXT,
  task        TEXT,
  held        INTEGER NOT NULL DEFAULT 0,
  reviewed    INTEGER NOT NULL DEFAULT 0,
  created     TEXT NOT NULL,
  done        TEXT,
  resolution  TEXT,
  steps       INTEGER,
  steps_done  INTEGER NOT NULL DEFAULT 0,
  taken       TEXT,
  taken_by    TEXT,
  position    INTEGER
);
CREATE TABLE IF NOT EXISTS work_links(
  work_id     TEXT NOT NULL REFERENCES work(work_id),
  number      INTEGER NOT NULL,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  PRIMARY KEY(work_id, number)
);
CREATE TABLE IF NOT EXISTS work_steps(
  row     INTEGER PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES work(work_id),
  number  INTEGER NOT NULL,
  said    TEXT,
  at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS work_steps_by_work ON work_steps(work_id, number);
CREATE TABLE IF NOT EXISTS messages(
  row         INTEGER PRIMARY KEY,
  message_id  TEXT NOT NULL UNIQUE,
  target_kind TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  kind        TEXT NOT NULL,
  text        TEXT,
  suggestions TEXT,
  by          TEXT,
  created     TEXT NOT NULL,
  closed      TEXT,
  answer      TEXT
);
CREATE INDEX IF NOT EXISTS messages_by_target ON messages(target_kind, target_id, row);
CREATE INDEX IF NOT EXISTS messages_by_closed ON messages(closed, row);
CREATE INDEX IF NOT EXISTS work_by_target ON work(target_kind, target_id, row);
CREATE INDEX IF NOT EXISTS work_by_condition ON work(condition, row);
CREATE INDEX IF NOT EXISTS work_by_done ON work(done, row);

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
