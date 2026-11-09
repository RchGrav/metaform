fn main() {
    let off = roundtable::prompts::process("A, B", "A", "/ws", true, false);
    let on = roundtable::prompts::process("A, B", "A", "/ws", true, true);
    let off_has = off.contains("Tools:");
    let on_has = on.contains("advance") && on.contains("feedback");
    let clean = !off.contains("advance") && !off.contains("feedback");
    println!("tools=false has Tools line: {off_has} (want false)");
    println!("tools=true has advance+feedback: {on_has} (want true)");
    println!("tools=false omits advance/feedback: {clean} (want true)");
    let ok = !off_has && on_has && clean;
    println!("F12 prompt gating correct: {ok}");
    std::process::exit(if ok {0} else {1});
}
