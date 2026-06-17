#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let _tray = tauri::tray::TrayIconBuilder::new()
                .tooltip("AI WorkDock")
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run AI WorkDock desktop app");
}
