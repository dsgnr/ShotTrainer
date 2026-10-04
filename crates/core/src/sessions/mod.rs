//! Session models and the SQLite database setup and migrations.

pub mod database;
pub mod models;

pub use database::{DatabaseError, Db, init_database, make_engine, migrate};
pub use models::{
    DATETIME_FORMAT, DEFAULT_SESSION_CATEGORY, SCHEMA_VERSION, SESSION_CATEGORIES, Session, Shot,
    format_datetime, parse_datetime, truncate_to_micros, utc_now,
};
