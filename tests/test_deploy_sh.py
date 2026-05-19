"""SoundGrabber Phase 14 — Wave 0 RED stubs.

Cobertura:
  AUTH-04 (D-01, D-02, D-04..D-07) -> bind mount `:ro` em api e worker, sg_tmp preservado,
                                        .env.example com valores corretos
  AUTH-05 (D-09)                    -> scripts/deploy.sh: set -e, chmod 750, git pull,
                                       docker compose up --build -d, sem eval

Run: pytest tests/test_deploy_sh.py -x -q
"""
from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPOSE_PATH = Path("docker-compose.yml")
ENV_EXAMPLE_PATH = Path(".env.example")
DEPLOY_SH_PATH = Path("scripts/deploy.sh")
PREDEPLOY_SH_PATH = Path("scripts/predeploy-check.sh")
OPS_CHECK_SH_PATH = Path("scripts/ops-check.sh")


def _load_compose() -> dict:
    """Parse docker-compose.yml com yaml.safe_load."""
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# AUTH-04: bind mount /data/yt-dlp-cache nos serviços api e worker
# ---------------------------------------------------------------------------

def test_bind_mount_in_compose_api():
    """D-01/D-04: serviço `api` deve ter volume '/data/yt-dlp-cache:/data/yt-dlp-cache:ro'."""
    compose = _load_compose()
    api_volumes = compose["services"]["api"].get("volumes", [])
    assert "/data/yt-dlp-cache:/data/yt-dlp-cache:ro" in api_volumes, (
        f"Expected bind mount '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in api service, "
        f"got {api_volumes}"
    )


def test_bind_mount_in_compose_worker():
    """D-01/D-05: serviço `worker` deve ter volume '/data/yt-dlp-cache:/data/yt-dlp-cache:ro'."""
    compose = _load_compose()
    worker_volumes = compose["services"]["worker"].get("volumes", [])
    assert "/data/yt-dlp-cache:/data/yt-dlp-cache:ro" in worker_volumes, (
        f"Expected bind mount '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in worker service, "
        f"got {worker_volumes}"
    )


def test_compose_preserves_sg_tmp_in_api():
    """D-06 (Pitfall 1): serviço `api` deve ter AMBOS 'sg_tmp:/tmp' E o bind mount.
    Falha se o bind mount ainda não foi adicionado (sg_tmp sozinho não basta).
    Quando Plan 02 adicionar o bind mount, este teste verifica que sg_tmp não foi removido."""
    compose = _load_compose()
    api_volumes = compose["services"]["api"].get("volumes", [])
    # Requer os dois volumes simultaneamente — RED até Plan 02 adicionar o bind mount
    assert "/data/yt-dlp-cache:/data/yt-dlp-cache:ro" in api_volumes and "sg_tmp:/tmp" in api_volumes, (
        f"Expected BOTH 'sg_tmp:/tmp' AND '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in api "
        f"service (Pitfall 1: bind mount não deve substituir sg_tmp), got {api_volumes}"
    )


def test_compose_preserves_sg_tmp_in_worker():
    """D-07 (Pitfall 1): serviço `worker` deve ter AMBOS 'sg_tmp:/tmp' E o bind mount.
    Falha se o bind mount ainda não foi adicionado (sg_tmp sozinho não basta).
    Quando Plan 02 adicionar o bind mount, este teste verifica que sg_tmp não foi removido."""
    compose = _load_compose()
    worker_volumes = compose["services"]["worker"].get("volumes", [])
    # Requer os dois volumes simultaneamente — RED até Plan 02 adicionar o bind mount
    assert "/data/yt-dlp-cache:/data/yt-dlp-cache:ro" in worker_volumes and "sg_tmp:/tmp" in worker_volumes, (
        f"Expected BOTH 'sg_tmp:/tmp' AND '/data/yt-dlp-cache:/data/yt-dlp-cache:ro' in worker "
        f"service (Pitfall 1: bind mount não deve substituir sg_tmp), got {worker_volumes}"
    )


def test_env_example_ytdlp_cache_dir():
    """D-02: .env.example deve conter 'YTDLP_CACHE_DIR=/data/yt-dlp-cache' (não vazio)."""
    env_text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert "YTDLP_CACHE_DIR=/data/yt-dlp-cache" in env_text, (
        "Expected 'YTDLP_CACHE_DIR=/data/yt-dlp-cache' in .env.example, "
        f"but found: {[l for l in env_text.splitlines() if 'YTDLP_CACHE_DIR' in l]}"
    )


def test_env_example_bgutil_empty():
    """D-09: .env.example deve ter 'BGUTIL_BASE_URL=' com valor vazio (sem URL bgutil no notebook)."""
    env_text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    # Encontra a linha que começa com BGUTIL_BASE_URL=
    bgutil_lines = [
        line for line in env_text.splitlines()
        if line.startswith("BGUTIL_BASE_URL=")
    ]
    assert bgutil_lines, "Expected BGUTIL_BASE_URL= line in .env.example but not found"
    bgutil_line = bgutil_lines[0]
    value_after_eq = bgutil_line.split("=", 1)[1].strip()
    assert value_after_eq == "", (
        f"Expected 'BGUTIL_BASE_URL=' with empty value in .env.example, "
        f"got '{bgutil_line}' (value after '=' is '{value_after_eq}')"
    )


# ---------------------------------------------------------------------------
# AUTH-05: scripts/deploy.sh existe e contém os controles de segurança
# ---------------------------------------------------------------------------

def test_deploy_sh_exists_and_has_set_e():
    """AUTH-05: scripts/deploy.sh deve existir e conter 'set -e' como primeira instrução executável."""
    assert DEPLOY_SH_PATH.exists(), (
        "scripts/deploy.sh não existe — crie o arquivo em scripts/deploy.sh"
    )
    script_text = DEPLOY_SH_PATH.read_text(encoding="utf-8")
    lines = script_text.splitlines()
    # Encontra a primeira linha não-shebang e não-comentário e não-vazia
    executable_lines = [
        line for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    assert executable_lines, (
        "scripts/deploy.sh existe mas não tem linhas executáveis após shebang/comentários"
    )
    first_executable = executable_lines[0].strip()
    assert first_executable == "set -e", (
        f"Expected first executable line to be 'set -e', got '{first_executable}'"
    )


def test_deploy_sh_security_gate_and_commands():
    """AUTH-05: scripts/deploy.sh deve ter chmod 750, cd ~/soundgrabber, git pull,
    sudo docker compose up --build -d; e NÃO deve conter 'eval'."""
    assert DEPLOY_SH_PATH.exists(), (
        "scripts/deploy.sh não existe — crie o arquivo em scripts/deploy.sh"
    )
    script_text = DEPLOY_SH_PATH.read_text(encoding="utf-8")

    required_substrings = [
        'chmod 750 "$(realpath "$0")"',
        "cd ~/soundgrabber",
        "git pull",
        "bash scripts/predeploy-check.sh",
        "sudo docker compose up --build -d",
    ]
    for substr in required_substrings:
        assert substr in script_text, (
            f"Expected substring '{substr}' in scripts/deploy.sh but not found"
        )

    assert "eval" not in script_text, (
        "scripts/deploy.sh contém 'eval' — uso proibido pelo Security Gate (CLAUDE.md)"
    )


def test_predeploy_check_blocks_unsafe_production_config():
    """Deploy gate deve validar checklist de seguranca antes do compose up."""
    assert PREDEPLOY_SH_PATH.exists(), "scripts/predeploy-check.sh deve existir"
    script_text = PREDEPLOY_SH_PATH.read_text(encoding="utf-8")

    required_substrings = [
        "DEV_MODE",
        'DEV_MODE precisa ser false',
        "REDIS_PASSWORD",
        "REDIS_URL precisa incluir senha Redis",
        "CLOUDFLARE_ACCESS_YONKOU_ENABLED",
        "ORIGIN_LOCKDOWN_ENABLED",
        "SECRETS_ROTATED_AFTER_AUDIT",
        "MONITORING_ENABLED",
        "BACKUP_ENCRYPTED_OFF_GIT",
        "-r requirements.txt",
        "docker compose config --quiet",
        "tests/test_security.py tests/test_deploy_sh.py",
    ]
    for substr in required_substrings:
        assert substr in script_text, f"predeploy-check sem controle esperado: {substr}"

    assert "eval" not in script_text


def test_ops_check_covers_runtime_observability():
    """Script operacional deve mostrar fila, disco/tmp, CPU/RAM e logs recentes."""
    assert OPS_CHECK_SH_PATH.exists(), "scripts/ops-check.sh deve existir"
    script_text = OPS_CHECK_SH_PATH.read_text(encoding="utf-8")

    required_substrings = [
        "/health",
        "llen celery",
        "df -h /tmp",
        "docker stats --no-stream",
        "docker compose logs --since=30m api worker",
    ]
    for substr in required_substrings:
        assert substr in script_text, f"ops-check sem observabilidade esperada: {substr}"

    assert "eval" not in script_text
