//! The Tauri application.

use crate::logging;

pub fn run() {
    logging::init();
    let app = tauri::Builder::default().build(tauri::generate_context!());
    match app {
        Ok(app) => app.run(|_, _| {}),
        Err(error) => {
            log::error!("Could not start ShotTrainer: {error}");
            std::process::exit(1);
        }
    }
}
