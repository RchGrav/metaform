//! Agent names from the genesis session (owner doc `archaeology/rich/technical/agent_identity.md`):
//! "An agent is born with its genesis context, the first session a harness opens for it. The id
//! of that session is the seed of the agent's identity." 32-bit FNV-1a of the id's UTF-8 bytes,
//! XOR-folded to 16 bits; the high byte picks one of 256 adjectives, the low byte one of 256
//! nouns, each capitalized and joined. The same id always gives the same name; two agents can
//! share a name and nothing rehashes. The word lists are the owner's.

const ADJECTIVES: &str = include_str!("../resources/names/adjectives.txt");
const NOUNS: &str = include_str!("../resources/names/nouns.txt");

pub fn genesis_name(session_id: &str) -> String {
    let mut hashed: u32 = 2_166_136_261;
    for byte in session_id.as_bytes() {
        hashed = (hashed ^ u32::from(*byte)).wrapping_mul(16_777_619);
    }
    let folded = (hashed ^ (hashed >> 16)) & 0xFFFF;
    let pick = |list: &str, index: u32| capitalize(list.lines().filter(|l| !l.trim().is_empty()).nth(index as usize).unwrap_or("agent").trim());
    pick(ADJECTIVES, folded >> 8) + &pick(NOUNS, folded & 0xFF)
}

fn capitalize(word: &str) -> String {
    let mut chars = word.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
        None => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_are_a_pure_function_of_the_session_id() {
        assert_eq!(ADJECTIVES.lines().count(), 256);
        assert_eq!(NOUNS.lines().count(), 256);
        let a = genesis_name("01a1ae33-9d9f-76e1-bfbf-37eb6d762b7e");
        assert_eq!(a, genesis_name("01a1ae33-9d9f-76e1-bfbf-37eb6d762b7e"));
        // Same answer as the owner's reference implementation (dispatch/names.py session_name).
        assert_eq!(a, "DeadeyeQuokka");
        assert!(a.chars().next().unwrap().is_uppercase());
        assert_ne!(a, genesis_name("another-session"));
    }
}
