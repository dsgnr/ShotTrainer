BEGIN TRANSACTION;
CREATE TABLE schema_meta (
    id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    PRIMARY KEY (id)
);
INSERT INTO "schema_meta" VALUES(1,3,'0.0.0');
CREATE TABLE sessions (
    id INTEGER NOT NULL,
    name VARCHAR(120) NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    notes TEXT NOT NULL,
    target_profile VARCHAR(64) NOT NULL,
    category VARCHAR(16) NOT NULL,
    app_version VARCHAR(32) NOT NULL,
    schema_version INTEGER NOT NULL,
    PRIMARY KEY (id)
);
INSERT INTO "sessions" VALUES(1,'session 1','2026-01-02 03:04:05.678901','2026-01-02 03:34:05.000001','','nsra-25yd','practice','0.0.0',3);
INSERT INTO "sessions" VALUES(2,'session 2','2026-01-03 10:00:00.000000',NULL,'','nsra-25yd','match','0.0.0',3);
CREATE TABLE shots (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    audio_level FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    score VARCHAR(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
);
INSERT INTO "shots" VALUES(1,1,0.1,1.5,-2.0,0.42,0.9,'9');
INSERT INTO "shots" VALUES(2,1,0.2,0.5,0.5,0.61,0.95,'10');
INSERT INTO "shots" VALUES(3,2,0.3,NULL,NULL,0.5,0.0,'');
CREATE TABLE trace_samples (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    ts FLOAT NOT NULL,
    x_px FLOAT NOT NULL,
    y_px FLOAT NOT NULL,
    x_mm FLOAT,
    y_mm FLOAT,
    confidence FLOAT NOT NULL,
    frame_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(session_id) REFERENCES sessions (id) ON DELETE CASCADE
);
INSERT INTO "trace_samples" VALUES(1,1,0.0,100.0,200.0,0.0,0.0,0.8,0);
INSERT INTO "trace_samples" VALUES(2,1,0.05,101.0,201.0,1.0,-1.0,0.8,1);
INSERT INTO "trace_samples" VALUES(3,1,0.1,102.0,202.0,2.0,-2.0,0.8,2);
INSERT INTO "trace_samples" VALUES(4,1,0.15000000000000002,103.0,203.0,3.0,-3.0,0.8,3);
INSERT INTO "trace_samples" VALUES(5,1,0.2,104.0,204.0,NULL,NULL,0.8,4);
CREATE INDEX ix_trace_session_ts ON trace_samples (session_id, ts);
CREATE INDEX ix_shots_session_id ON shots (session_id);
COMMIT;
