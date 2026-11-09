#[path = "../../crates/acp-host/src/permission.rs"]
mod permission;
use permission::{PermissionAsk,PermissionPolicy,ScopePolicy};
fn main() -> std::io::Result<()> {
    let fixture=std::env::current_dir()?.join("review/round2/scope-fixture");
    let root=fixture.join("root");
    std::fs::create_dir_all(&root)?;
    let outside=fixture.join("missing-outside.txt");
    let link=root.join("link");
    if link.symlink_metadata().is_ok() { std::fs::remove_file(&link)?; }
    assert!(!outside.exists());
    std::os::unix::fs::symlink(&outside,&link)?;
    let policy=ScopePolicy::new(&root);
    let ask=PermissionAsk {title:None,kind:Some("edit".into()),locations:vec![link.clone()],cwd:root};
    println!("dangling outside target: {:?}",policy.decide(&ask));
    std::fs::remove_file(link)?;
    Ok(())
}
