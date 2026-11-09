//! The saved settings: only the values the chair set, in one JSON file in Roundtable's home
//! folder. One writer at a time; each write replaces the file whole.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::Mutex;

use serde::Serialize;

use super::{Kind, SETTINGS, Setting, Value, find};
use crate::config::TableConfig;

/// Where a value came from.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Source {
    Default,
    /// Saved by the chair in the settings file.
    Saved,
    /// Given for one table only.
    Table,
}

/// One setting as listed.
#[derive(Debug, Clone, Serialize)]
pub struct Row {
    pub key: &'static str,
    pub group: &'static str,
    pub value: String,
    pub default: &'static str,
    pub source: Source,
    pub summary: &'static str,
    pub allowed: String,
    pub gate: Option<&'static str>,
}

/// What a change did to one key.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Change {
    pub key: String,
    pub old: String,
    pub new: String,
}

pub struct Store {
    path: PathBuf,
    saved: Mutex<BTreeMap<String, String>>,
}

impl Store {
    /// Read the settings file. A missing file is no saved settings. A saved value that no
    /// longer validates, or an unknown key, is reported and left out, so its default applies.
    pub fn open(path: PathBuf) -> (Self, Vec<String>) {
        let mut problems = Vec::new();
        let mut saved = BTreeMap::new();
        match std::fs::read_to_string(&path) {
            Ok(text) => match serde_json::from_str::<BTreeMap<String, String>>(&text) {
                Ok(map) => {
                    for (key, raw) in map {
                        match find(&key).map(|s| s.parse(&raw)) {
                            Some(Ok(value)) => {
                                saved.insert(key, value.text());
                            }
                            Some(Err(error)) => problems.push(format!("{}: {error}; using the default", path.display())),
                            None => problems.push(format!("{}: unknown setting {key:?} ignored", path.display())),
                        }
                    }
                }
                Err(error) => problems.push(format!("{} is not a JSON object of settings ({error}); using the defaults", path.display())),
            },
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => problems.push(format!("{} could not be read ({error}); using the defaults", path.display())),
        }
        (Self { path, saved: Mutex::new(saved) }, problems)
    }

    fn setting(key: &str) -> Result<&'static Setting, String> {
        find(key).ok_or_else(|| format!("no setting is called {key:?}"))
    }

    /// The value in effect and where it came from.
    pub fn get(&self, key: &str) -> Result<(Value, Source), String> {
        let setting = Self::setting(key)?;
        Ok(match self.saved.lock().unwrap().get(key) {
            Some(raw) => (setting.parse(raw)?, Source::Saved),
            None => (setting.default_value(), Source::Default),
        })
    }

    /// Save a value. Refused, with the allowed form, when it does not validate.
    pub fn set(&self, key: &str, raw: &str) -> Result<Change, String> {
        let setting = Self::setting(key)?;
        let value = setting.parse(raw)?;
        let mut saved = self.saved.lock().unwrap();
        let old = saved.get(key).cloned().unwrap_or_else(|| setting.default_value().text());
        let mut next = saved.clone();
        next.insert(key.to_string(), value.text());
        self.write(&next)?;
        *saved = next;
        Ok(Change { key: key.into(), old, new: value.text() })
    }

    /// Restore a key's default, or every default with `all`. Reports only keys that changed.
    pub fn unset(&self, key: &str) -> Result<Vec<Change>, String> {
        let mut saved = self.saved.lock().unwrap();
        let keys: Vec<String> = if key == "all" {
            saved.keys().cloned().collect()
        } else {
            Self::setting(key)?;
            saved.contains_key(key).then(|| key.to_string()).into_iter().collect()
        };
        let mut next = saved.clone();
        let mut changes = Vec::new();
        for key in keys {
            let default = Self::setting(&key)?.default_value().text();
            if let Some(old) = next.remove(&key).filter(|old| *old != default) {
                changes.push(Change { key, old, new: default });
            }
        }
        self.write(&next)?;
        *saved = next;
        Ok(changes)
    }

    fn write(&self, values: &BTreeMap<String, String>) -> Result<(), String> {
        let fail = |e: std::io::Error| format!("the settings could not be saved to {}: {e}", self.path.display());
        if let Some(dir) = self.path.parent() {
            std::fs::create_dir_all(dir).map_err(fail)?;
        }
        let temporary = self.path.with_extension("json.tmp");
        std::fs::write(&temporary, serde_json::to_string_pretty(values).expect("strings serialise")).map_err(fail)?;
        std::fs::rename(&temporary, &self.path).map_err(fail)
    }

    /// Every setting with its value, default and source. `run` holds one table's values,
    /// which are listed with the source `table`.
    pub fn list(&self, run: &BTreeMap<String, String>) -> Result<Vec<Row>, String> {
        let saved = self.saved.lock().unwrap();
        SETTINGS
            .iter()
            .map(|s| {
                let (value, source) = match (run.get(s.key), saved.get(s.key)) {
                    (Some(raw), _) => (s.parse(raw)?.text(), Source::Table),
                    (None, Some(raw)) => (raw.clone(), Source::Saved),
                    (None, None) => (s.default_value().text(), Source::Default),
                };
                Ok(Row { key: s.key, group: s.group(), value, default: s.default, source, summary: s.summary, allowed: allowed(s), gate: s.gate })
            })
            .collect()
    }

    /// Fill a table's configuration from every setting: the table's own value from `run` when
    /// given, else the saved value, else the default. An unknown key or a bad value in `run`
    /// refuses the table, naming the problem.
    pub fn apply(&self, config: &mut TableConfig, run: &BTreeMap<String, String>) -> Result<(), String> {
        if let Some(unknown) = run.keys().find(|k| find(k).is_none()) {
            return Err(format!("no setting is called {unknown:?}"));
        }
        for setting in SETTINGS {
            let value = match run.get(setting.key) {
                Some(raw) => setting.parse(raw)?,
                None => self.get(setting.key)?.0,
            };
            (setting.apply)(config, &value);
        }
        Ok(())
    }
}

/// The allowed values, in words, for the list and the settings page.
fn allowed(s: &Setting) -> String {
    match s.kind {
        Kind::Bool => "on or off".into(),
        Kind::Count { min, max } => format!("{min} to {max}"),
        Kind::CountOrOff { min, max } => format!("{min} to {max}, or off"),
        Kind::Choice(words) => words.join(", "),
        Kind::Scope => "workspace, project, or an absolute path".into(),
    }
}
