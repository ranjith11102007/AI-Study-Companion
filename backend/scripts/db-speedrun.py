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

fh = open(LOGFILE, "a", encoding="utf-8")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


async def pg_connect(user, dbname, password=None, timeout=5, retries=3, gap=1.0):
    last = None
    for _ in range(retries):
        try:
            kwargs = dict(host="127.0.0.1", port=5432, user=user,
                          database=dbname, timeout=timeout)
            if password:
                kwargs["password"] = password
            return await asyncio.wait_for(asyncpg.connect(**kwargs), timeout=timeout + 2)
        except Exception as e:
            last = e
            await asyncio.sleep(gap)
    raise last


async def main() -> int:
    log("---- speedrun start ----")
    try:
        admin = await pg_connect("postgres", "postgres", retries=4, gap=0.5)
    except Exception as e:
        log(f"admin connect failed: {type(e).__name__}")
        return 1
    try:
        try:
            await admin.execute("CREATE ROLE studymate WITH LOGIN PASSWORD 'studymate' CREATEDB")
            log("role studymate: created")
        except asyncpg.DuplicateObjectError:
            log("role studymate: exists")
        try:
            await admin.execute("CREATE DATABASE studymate OWNER studymate")
            log("database studymate: created")
        except asyncpg.DuplicateDatabaseError:
            log("database studymate: exists")
    except Exception as e:
        log(f"role/db failed: {type(e).__name__}: {e}")
        return 1
    finally:
        await admin.close()

    try:
        c = await pg_connect("studymate", "studymate", "studymate", retries=3, gap=0.5)
        await c.close()
        log("studymate login: OK")
    except Exception as e:
        log(f"studymate login failed: {type(e).__name__}")
        return 1

    alembic = BACKEND / ".venv" / "Scripts" / "alembic.exe"
    if alembic.exists():
        cmd = [str(alembic)]
    else:
        cmd = [sys.executable, "-c",
               "import sys; from alembic.config import main; main(sys.argv[1:])"]
    try:
        r = await asyncio.to_thread(
            lambda: subprocess.run(cmd + ["upgrade", "head"], cwd=str(BACKEND),
                                   capture_output=True, text=True, timeout=120))
    except Exception as e:
        log(f"alembic exec failed: {type(e).__name__}: {e}")
        return 2
    if r.returncode != 0:
        log(f"alembic FAIL rc={r.returncode} out={(r.stdout or '')[-300:]} err={(r.stderr or '')[-300:]}")
        return 2
    log("alembic upgrade head: OK")

    try:
        c = await pg_connect("studymate", "studymate", "studymate", retries=4, gap=1.0)
    except Exception as e:
        log(f"verify connect failed: {type(e).__name__}")
        return 3
    try:
        rows = await c.fetch("select tablename from pg_tables where schemaname='public'")
        have = {r[0] for r in rows}
        missing = EXPECTED_TABLES - have
        ext = await c.fetchval("select count(*) from pg_extension where extname='vector'")
        idx = await c.fetchval(
            "select count(*) from pg_indexes where schemaname='public' "
            "and indexname = 'ix_content_embeddings_embedding'")
        log(f"tables={sorted(have)}")
        log(f"vector_ext={ext} hnsw_index={idx}")
        if missing or ext != 1:
            log(f"verify FAILED missing={sorted(missing)}")
            return 3

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
            "insert into content_units (material_id, course_id, content_type, title, "
            "content, page_number, metadata) values ($1,$2,$3,$4,$5,$6,$7::jsonb) returning id",
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
        log(f"smoke OK: vector cosine distance={dist}, rows after rollback={after}")
        if after != 0:
            log("rollback FAILED")
            return 4
    except Exception as e:
        log(f"smoke FAILED: {type(e).__name__}: {e}")
        try:
            await c.execute("ROLLBACK")
        except Exception:
            pass
        return 4
    finally:
        await c.close()

    log("COMPLETE: database foundation ready")
    return 0


code = asyncio.run(main())
fh.close()
sys.exit(code)
