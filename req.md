     Implementation Phases

     Phase 1: Database Infrastructure

     1. Add sqlalchemy, aiosqlite, alembic to agent-service/requirements.txt
     2. Create database.py with async engine and session factory
     3. Define models in models/db.py
     4. Set up Alembic for migrations
     5. Create initial migration for sessions and runs tables

     Phase 2: Repository Layer

     1. Create repositories/session_repository.py with CRUD:
       - create_session(session_id, title)
       - get_session(session_id)
       - list_sessions()
       - delete_session(session_id) (soft delete)
       - get_session_runs(session_id)
     2. Create repositories/run_repository.py with CRUD:
       - create_run(run_id, session_id, query)
       - get_run(run_id)
       - update_run(run_id, **updates)
       - get_run_report(run_id)

     Phase 3: Router Refactoring

     1. routers/sessions.py: Replace dict operations with repository calls
     2. routers/runs.py:
       - Keep _run_states for active streaming runs (in-memory for performance)
       - Persist run state to DB on creation and completion
       - Load historical runs from DB on demand

     Phase 4: Session History Loading

     1. Add GET /sessions/{session_id} endpoint to load full session with runs
     2. Frontend can fetch historical sessions on mount (optional enhancement)

     Verification Steps

     1. Schema Verification: Run alembic upgrade head, verify data/agent.db created
     2. Session Creation: Call POST /agent/sessions, verify DB row inserted
     3. Run Execution: Start a run, verify runs table updated on completion
     4. Persistence Test: Restart server, verify sessions still queryable
     5. Frontend Test: Open frontend, create sessions, refresh page, verify sessions persist
     6. Sidebar Test: Verify all persisted sessions appear as sidebar tabs

     Optional Enhancements (Post-MVP)

     1. Session Title Generation: Call LLM to generate titles from first query
     2. Full-Text Search: Add FTS index on runs.query for search functionality
     3. PostgreSQL Migration: Change DATABASE_URL if scaling needed
     4. Run Streaming Snapshots: Periodically save streaming state to DB

