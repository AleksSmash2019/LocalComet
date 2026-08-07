// Build: Tauri binaries get a comctl32 v6 manifest via `cargo:rustc-link-arg-bins`,
// but lib test harnesses do not. On Windows MSVC without that manifest a hard
// import of TaskDialogIndirect (via WRY/webview2) faults 0xC0000139 at loader
// time. Delay-load defers the binding — tests never call TaskDialogIndirect, so
// the loader succeeds. That is why the production exe also benefits.
// Fix validated: only Windows MSVC needs /DELAYLOAD + delayimp.lib; GNU has
// different import mechanics. Target narrowing uses compile-time cfg so the
// linker flag is never emitted where it cannot apply.

#[cfg(all(target_os = "windows", target_env = "msvc"))]
fn emit_msvc_delayload() {
    println!("cargo:rustc-link-arg=/DELAYLOAD:comctl32.dll");
    println!("cargo:rustc-link-arg=delayimp.lib");
}

fn main() {
    tauri_build::build();
    #[cfg(all(target_os = "windows", target_env = "msvc"))]
    emit_msvc_delayload();
}
