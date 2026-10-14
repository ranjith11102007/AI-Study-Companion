import asyncio
import asyncpg
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(r"C:\Users\RANJITH T\Desktop\AI-Study-Companion\backend")
LOGFILE = Path(__import__("tempfile").gettempdir()) / "studymate-quick.log"
fh = open(LOGFILE, "w", encoding="utf-8")


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    fh.write(line + "\n")
    fh.flush()


async def pg_connect(user, dbname, password=None, timeout=6):
    kwargs = dict(host="127.0.0.1", port=5432, user=user, database=dbname, timeout=timeout)
    if password:
        kwargs["password"] = password
    return await asyncio.wait_for(asyncpg.connect(**kwargs), timeout=timeout + 2)


async def main() -> int:
    try:
        c = await pg_connect("studymate", "studymate", "studymate")
        log("connect studymate: OK")
    except Exception as e:
        log(f"connect studymate: FAIL {type(e).__name__}: {e}")
        return 1

    try:
        admin = await pg_connect("postgres", "postgres")
        try:
            await admin.execute("CREATE ROLE studymate WITH LOGIN PASSWORD 'studymate' CREATEDB")
            log("role created")
        except asyncpg.DuplicateObjectError:
            log("role exists")
        try:
            await admin.execute("CREATE DATABASE studymate OWNER studymate")
            log("database created")
        except asyncpg.DuplicateDatabaseError:
            log("database exists")
        await admin.close()
    except Exception as e:
        log(f"role/db step: {type(e).__name__}: {e}")
        return 2

    await c.close()
    c = await pg_connect("studymate", "studymate", "studymate")

    alembic = BACKEND / ".venv" / "Scripts" / "alembic.exe"
    if alembic.exists():
        cmd = [str(alembic)]
    else:
        cmd = [sys.executable, "-c",
               "import sys; from alembic.config import main; main(sys.argv[1:])"]
    r = subprocess.run(cmd + ["upgrade", "head"], cwd=str(BACKEND),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"alembic FAIL rc={r.returncode} out={(r.stdout or '')[-400:]} err={(r.stderr or '')[-400:]}")
        return 3
    log("alembic upgrade head: OK")

    tables = [x[0] for x in await c.fetch(
        "select tablename from pg_tables where schemaname='public' order by 1")]
    ext = await c.fetchval("select count(*) from pg_extension where extname='vector'")
    idx = [x[0] for x in await c.fetch(
        "select indexname from pg_indexes where schemaname='public' "
        "and indexname = 'ix_content_embeddings_embedding'")]
    expected = {"users", "courses", "learning_materials", "content_units",
                "topics", "content_unit_topics", "content_embeddings"}
    log(f"tables={tables}")
    log(f"vector_ext={ext} hnsw={idx}")
    if not expected.issubset(set(tables)) or ext != 1:
        log("schema verification FAILED")
        return 4
    log("schema verification: OK")

    await c.execute("BEGIN")
    uid = await c.fetchval(
        "insert into users (email, password_hash, display_name, is_active) "
        "values ($1,$2,$3,true) returning id", "smoke@test.local", "h" * 60, "Smoke")
    cid = await c.fetchval(
        "insert into courses (user_id, title) values ($1,$2) returning id", uid, "Smoke Course")
    mid = await c.fetchval(
        "insert into learning_materials (course_id, filename, source_type, status) "
        "values ($1,$2,$3,'ready') returning id", cid, "smoke.pdf", "pdf")
    unit = await c.fetchval(
        "insert into content_units (material_id, unit_index, content, char_count) "
        "values ($1,0,$2,$3) returning id", mid, "Smoke content.", 13)
    tid = await c.fetchval(
        "insert into topics (course_id, name) values ($1,$2) returning id", cid, "smoke")
    await c.execute(
        "insert into content_unit_topics (content_unit_id, topic_id) values ($1,$2)", unit, tid)
    vec = "[" + ",".join(["0.5"] * 768) + "]"
    await c.execute(
        "insert into content_embeddings (content_unit_id, embedding, model) "
        "values ($1, $2::vector, $3)", unit, vec, "nomic-embed-text")
    dist = await c.fetchval(
        "select embedding <=> $1::vector from content_embeddings where content_unit_id=$2",
        vec, unit)
    await c.execute("ROLLBACK")
    after = await c.fetchval("select count(*) from content_embeddings")
    log(f"smoke insert + vector cosine distance={dist}; rows after rollback={after}")
    await c.close()
    if after != 0:
        log("rollback FAILED")
        return 5
    log("ALL OK: database foundation verified end-to-end")
    return 0


code = asyncio.run(main())
fh.close()
sys.exit(code)
