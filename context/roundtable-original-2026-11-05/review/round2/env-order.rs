fn main() {
    // Synthetic variable only; do not print the real inherited environment.
    let output=std::process::Command::new("/usr/bin/env")
        .env("ROUNDTABLE_REVIEW_KEY", "synthetic")
        .env_remove("ROUNDTABLE_REVIEW_KEY")
        .output().unwrap();
    let present=String::from_utf8(output.stdout).unwrap()
        .lines().any(|line|line.starts_with("ROUNDTABLE_REVIEW_KEY="));
    println!("explicit synthetic key survives env_remove: {present}");
}
