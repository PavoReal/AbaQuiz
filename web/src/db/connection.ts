import { Database } from "bun:sqlite";

const DATABASE_PATH = process.env.DATABASE_PATH || "../data/abaquiz.db";

let _db: Database | null = null;

/**
 * Get the database instance.
 * Creates the connection if it doesn't exist.
 */
export function getDb(): Database {
  if (!_db) {
    throw new Error("Database not initialized. Call initDb() first.");
  }
  return _db;
}

/**
 * Initialize the database connection with WAL mode.
 */
export async function initDb(): Promise<void> {
  console.log(`Connecting to database at: ${DATABASE_PATH}`);

  _db = new Database(DATABASE_PATH, {
    readwrite: true,
    create: false, // Don't create if doesn't exist - Python bot manages schema
  });

  // Enable WAL mode for concurrent read access
  _db.run("PRAGMA journal_mode=WAL");
  _db.run("PRAGMA busy_timeout=5000"); // Wait up to 5s for locks
  _db.run("PRAGMA synchronous=NORMAL"); // Balance durability/performance
  _db.run("PRAGMA foreign_keys=ON");

  console.log("Database connected with WAL mode enabled");

  // Run migrations for new queue tables
  await runMigrations(_db);
}

/**
 * Close the database connection.
 */
export function closeDb(): void {
  if (_db) {
    // Checkpoint WAL before closing
    _db.run("PRAGMA wal_checkpoint(TRUNCATE)");
    _db.close();
    _db = null;
    console.log("Database connection closed");
  }
}

/**
 * Run migrations for new queue tables needed by web admin.
 */
async function runMigrations(db: Database): Promise<void> {
  // Check if queue tables exist
  const tableCheck = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='broadcast_queue'"
    )
    .get() as { name: string } | undefined;

  if (!tableCheck) {
    console.log("Creating broadcast_queue table...");
    db.run(`
      CREATE TABLE IF NOT EXISTS broadcast_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_text TEXT NOT NULL,
        message_format TEXT DEFAULT 'text',
        target_filter TEXT DEFAULT 'all',
        target_user_ids TEXT,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        processed_at TIMESTAMP,
        sent_count INTEGER DEFAULT 0,
        error_message TEXT
      )
    `);
  }

  const genQueueCheck = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_queue'"
    )
    .get() as { name: string } | undefined;

  if (!genQueueCheck) {
    console.log("Creating generation_queue table...");
    db.run(`
      CREATE TABLE IF NOT EXISTS generation_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requested_count INTEGER NOT NULL,
        skip_dedup BOOLEAN DEFAULT FALSE,
        distribution TEXT,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        generated_count INTEGER DEFAULT 0,
        duplicate_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        error_message TEXT
      )
    `);
  }

  const progressCheck = db
    .prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_progress'"
    )
    .get() as { name: string } | undefined;

  if (!progressCheck) {
    console.log("Creating generation_progress table...");
    db.run(`
      CREATE TABLE IF NOT EXISTS generation_progress (
        queue_id INTEGER PRIMARY KEY REFERENCES generation_queue(id),
        current_area TEXT,
        area_progress TEXT,
        total_generated INTEGER DEFAULT 0,
        total_duplicates INTEGER DEFAULT 0,
        total_errors INTEGER DEFAULT 0,
        estimated_cost REAL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
  }

  console.log("Database migrations complete");
}

// Export a convenience reference
export { _db as db };
