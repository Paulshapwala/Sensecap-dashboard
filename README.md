# Branch Strategy

## Sensecap v1
**Status:** STABLE CHECKPOINT (FROZEN)  
**Purpose:** Working reference point - never to be touched  
**Features:**
- Fully functional Docker containerization
- MQTT client receiving IoT data
- Redis pub/sub messaging
- SQLite database with persistence
- Real-time SSE updates
- Basic frontend (placeholder)

**Rules:**
- NEVER MODIFY - UNTOUCHABLE
- Use only as recovery reference if development goes wrong
- Can checkout from if needed to restart

**When to use:** Only if v1-development breaks beyond repair, checkout Sensecap v1 and restart development from there

---

## v1-development
**Status:** Active Backend Development  
**Purpose:** Improve and perfect the backend, then merge to master  
**Features:**
- Carbon copy of `Senscap v1`
- All docker infrastructure
- All MQTT/Redis functionality

**Rules:**
- Backend bug fixes allowed
- Improvements allowed (PostgreSQL, security, etc.)
- Refactoring allowed
- Do NOT add frontend code (master handles that)
- Merge to: `master` directly (when ready and tested)

**When to use:** Backend refinement, bug fixes, performance improvements

---

## master
**Status:** Production Branch  
**Purpose:** Integrate frontend client code with stable backend  
**Features:**
- Dracula theme UI
- Latest frontend client code
- Receives stable backend from v1-development

**Rules:**
- Frontend commits allowed
- Merge from: `v1-development` (stable backend)
- Do NOT directly modify backend code
- Backend changes only via v1-development merge

**When to use:** Production code, integrated frontend + backend system

---

## Merge Strategy

### Phase 1: Backend Development (Current)
```
v1-development → master (when backend improvements complete & tested)
```

### Phase 2: Ongoing
```
v1-development  ← Backend improvements/bug fixes
    ↓ (merge directly to master when satisfied)
master          ← Receives stable backend
    ↑ (frontend development happens here too)
Frontend team   ← Works on master for UI/client code
```

### If Things Break Badly
```
Sensecap v1 → checkout as recovery reference
→ Start over or debug from stable point
```

---

## Current Task
Work on `v1-development` to:
- [ ] Develop accounts app
- [ ] Fix AutoField warnings
- [ ] Switch to PostgreSQL - hosted on supabase
- [ ] Add security improvements
- [ ] finalize all data fields formats for waether app models
- [ ] Add documentation
- [ ] Test thoroughly

**Then:** Merge directly to master (no touching Senscap v1)

## How to use:
To use this branch git clone the repo and create a .env then run docker compose
Everything else has been setup and is ready to use.