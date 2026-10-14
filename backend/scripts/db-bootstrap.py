import asyncio
import asyncpg
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(r"C:\Users\RANJITH T\Desktop\AI-Study-Companion\backend")
LOGFILE = Path(__import__("tempfile").gettempdir()) / "studymate-dbops.log"

EXPECTED_TABLES = {
    "users", "courses", "learning_materials", "content_units",
    "topics", "content_unit_topics", "content_embeddings",
}


class Step:
    def __init__(self):
        self.fh = open(LOGFILE, "a", encoding="utf-8")

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


async def pg_connect(user, dbname, password=None, timeout=6):
    kwargs = dict(host="127.0.0.1", port=5432, user=user, database=dbname, timeout=timeout)
    if password:
        kwargs["password"] = password
    return await asyncio.wait_for(asyncpg.connect(**kwargs), timeout=timeout + 2)


async def ensure_role_db(s: Step) -> bool:
    try:
        admin = await pg_connect("postgres", "postgres")
    except Exception as e:
        s.log(f"admin connect failed: {type(e).__name__}")
        return False
    try:
        try:
            await admin.execute("CREATE ROLE studymate WITH LOGIN PASSWORD 'studymate' CREATEDB")
            s.log("role studymate: created")
        except asyncpg.DuplicateObjectError:
            s.log("role studymate: exists")
        try:
            await admin.execute("CREATE DATABASE studymate OWNER studymate")
            s.log("database studymate: created")
        except asyncpg.DuplicateDatabaseError:
            s.log("database studymate: exists")
    except Exception as e:
        s.log(f"role/db create failed: {type(e).__name__}: {e}")
        return False
    finally:
        await admin.close()
    try:
        c = await pg_connect("studymate", "studymate", "studymate")
        await c.close()
        s.log("studymate login: OK")
        return True
    except Exception as e:
        s.log(f"studymate login failed: {type(e).__name__}")
        return False


async def tables_exist(s: Step) -> bool:
    try:
        c = await pg_connect("studymate", "studymate", "studymate")
    except Exception as e:
        s.log(f"connect for verify failed: {type(e).__name__}")
        return False
    try:
        rows = await c.fetch(
            "select tablename from pg_tables where schemaname='public'")
        have = {r[0] for r in rows}
        missing = EXPECTED_TABLES - have
        if missing:
            s.log(f"schema incomplete; missing={sorted(missing)}")
            return False
        ext = await c.fetchval(
            "select count(*) from pg_extension where extname='vector'")
        if ext != 1:
            s.log("pgvector extension NOT installed in database")
            return False
        idx = await c.fetchval(
            "select count(*) from pg_indexes where schemaname='public' "
            "and indexname = 'ix_content_embeddings_embedding'")
        s.log(f"schema OK (tables present, vector={ext}, hnsw_index={idx})")
        return True
    finally:
        await c.close()


def run_alembic(s: Step) -> bool:
    alembic = BACKEND / ".venv" / "Scripts" / "alembic.exe"
    if alembic.exists():
        cmd = [str(alembic)]
    else:
        cmd = [sys.executable, "-c",
               "import sys; from alembic.config import main; main(sys.argv[1:])"]
    try:
        r = subprocess.run(cmd + ["upgrade", "head"], cwd=str(BACKEND),
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        s.log(f"alembic exec failed: {type(e).__name__}: {e}")
        return False
    if r.returncode != 0:
        s.log(f"alembic FAIL rc={r.returncode} out={(r.stdout or '')[-300:]} err={(r.stderr or '')[-300:]}")
        return False
    s.log("alembic upgrade head: OK")
    return True


async def smoke_test(s: Step) -> bool:
    try:
        c = await pg_connect("studymate", "studymate", "studymate")
    except Exception as e:
        s.log(f"smoke connect failed: {type(e).__name__}")
        return False
    try:
        await c.execute("BEGIN")
        uid = await c.fetchval(
            "insert into users (name, email, password_hash) values ($1,$2,$3) returning id",
            "Smoke", "smoke@test.local", "h" * 60)
        cid = await c.fetchval(
            "insert into courses (user_id, title) values ($1,$2) returning id",
            uid, "Smoke Course")
        mid = await c.fetchval(
            "insert into learning_materials (course_id, filename, original_filename, "
            "material_type, file_path, processing_status) values ($1,$2,$3,$4,$5,$6) returning id",
            cid, "abc123.pdf", "notes.pdf", "pdf", "data/uploads/abc123.pdf", "ready")
        unit = await c.fetchval(
            "insert into content_units (material_id, course_id, content_type, title, content, "
            "page_number, metadata) values ($1,$2,$3,$4,$5,$6,$7::jsonb) returning id",
            mid, cid, "text", "Intro", "Smoke content.", 1, '{"source": "test"}')
        tid = await c.fetchval(
            "insert into topics (course_id, name) values ($1,$2) returning id",
            cid, "smoke")
        await c.execute(
            "insert into content_unit_topics (content_unit_id, topic_id) values ($1,$2)",
            unit, tid)
        vec = "[" + ",".join(["0.5"] * 768) + "]"
        await c.execute(
            "insert into content_embeddings (content_unit_id, embedding, model) "
            "values ($1, $2::vector, $3)", unit, vec, "nomic-embed-text")
        dist = await c.fetchval(
            "select embedding <=> $1::vector from content_embeddings "
            "where content_unit_id=$2", vec, unit)
        await c.execute("ROLLBACK")
        after = await c.fetchval("select count(*) from content_embeddings")
        s.log(f"smoke insert OK; vector cosine distance={dist}; rows after rollback={after}")
        if after != 0:
            s.log("rollback FAILED")
            return False
        return True
    except Exception as e:
        s.log(f"smoke failed: {type(e).__name__}: {e}")
        try:
            await c.execute("ROLLBACK")
        except Exception:
            pass
        return False
    finally:
        await c.close()


async def main() -> int:
    s = Step()
    s.log("---- bootstrap run start ----")
    try:
        if not await ensure_role_db(s):
            return 1
        if await tables_exist(s):
            s.log("schema already present; skipping migration")
        else:
            if not run_alembic(s):
                return 2
            if not await tables_exist(s):
                s.log("schema still incomplete after migration")
                return 3
        if not await smoke_test(s):
            return 4
        s.log("COMPLETE: database foundation ready")
        return 0
    except Exception as e:
        s.log(f"UNHANDLED: {type(e).__name__}: {e}")
        return 9
    finally:
        s.close()


sys.exit(asyncio.run(main()))
