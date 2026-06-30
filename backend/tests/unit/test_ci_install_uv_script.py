from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2].parent


def test_install_uv_reuses_cached_binary_without_network(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "ci" / "install-uv.sh"
    install_dir = tmp_path / "uv"
    cache_dir = tmp_path / "cache"
    path_file = tmp_path / "github-path"
    fake_bin = tmp_path / "fake-bin"
    curl_marker = tmp_path / "curl-called"

    install_dir.mkdir()
    cache_dir.mkdir()
    fake_bin.mkdir()

    cached_uv = install_dir / "bin" / "uv"
    cached_uv.parent.mkdir(parents=True)
    cached_uv.write_text("#!/usr/bin/env bash\necho 'uv 9.9.9 cached'\n", encoding="utf-8")
    cached_uv.chmod(0o755)

    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env bash\n"
        f": > {curl_marker}\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "UV_INSTALL_DIR": str(install_dir),
            "UV_CACHE_DIR": str(cache_dir),
            "GITHUB_PATH": str(path_file),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Using cached uv from" in result.stdout
    assert not curl_marker.exists()
    assert path_file.read_text(encoding="utf-8") == f"{install_dir / 'bin'}\n"


def test_install_uv_bootstraps_cached_directory_when_missing(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "ci" / "install-uv.sh"
    install_dir = tmp_path / "uv"
    cache_dir = tmp_path / "cache"
    path_file = tmp_path / "github-path"
    fake_bin = tmp_path / "fake-bin"
    install_marker = tmp_path / "install-called"

    cache_dir.mkdir()
    fake_bin.mkdir()

    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "#!/usr/bin/env sh\n"
        f": > {install_marker}\n"
        'mkdir -p "$UV_UNMANAGED_INSTALL"\n'
        'cat > "$UV_UNMANAGED_INSTALL/uv" <<\'INNER\'\n'
        '#!/usr/bin/env bash\n'
        "echo 'uv 9.9.9 installed'\n"
        'INNER\n'
        'chmod +x "$UV_UNMANAGED_INSTALL/uv"\n'
        "EOF\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "UV_INSTALL_DIR": str(install_dir),
            "UV_CACHE_DIR": str(cache_dir),
            "GITHUB_PATH": str(path_file),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert install_marker.exists()
    assert "uv 9.9.9 installed" in result.stdout
    assert path_file.read_text(encoding="utf-8") == f"{install_dir / 'bin'}\n"


def test_install_uv_shields_uv_install_dir_from_installer(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "ci" / "install-uv.sh"
    install_dir = tmp_path / "uv"
    cache_dir = tmp_path / "cache"
    path_file = tmp_path / "github-path"
    fake_bin = tmp_path / "fake-bin"
    env_probe = tmp_path / "env.txt"

    cache_dir.mkdir()
    fake_bin.mkdir()

    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "#!/usr/bin/env sh\n"
        # Real uv installer prefers UV_INSTALL_DIR over UV_UNMANAGED_INSTALL and
        # treats it as a flat layout, so UV_INSTALL_DIR would land uv at
        # $UV_INSTALL_DIR/uv instead of $UV_INSTALL_DIR/bin/uv. The script must
        # shield the installer from inheriting UV_INSTALL_DIR.
        f'env > {env_probe}\n'
        'mkdir -p "$UV_UNMANAGED_INSTALL"\n'
        'cat > "$UV_UNMANAGED_INSTALL/uv" <<\'INNER\'\n'
        '#!/usr/bin/env bash\n'
        "echo 'uv 9.9.9 installed'\n"
        'INNER\n'
        'chmod +x "$UV_UNMANAGED_INSTALL/uv"\n'
        "EOF\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "UV_INSTALL_DIR": str(install_dir),
            "UV_CACHE_DIR": str(cache_dir),
            "GITHUB_PATH": str(path_file),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert env_probe.exists(), "installer was not invoked"
    probe_lines = {
        line.split("=", 1)[0] for line in env_probe.read_text(encoding="utf-8").splitlines() if "=" in line
    }
    assert "UV_INSTALL_DIR" not in probe_lines, (
        "install-uv.sh leaked UV_INSTALL_DIR into the installer environment; "
        "uv would install flat at $UV_INSTALL_DIR/uv instead of $UV_INSTALL_DIR/bin/uv"
    )
    assert "UV_UNMANAGED_INSTALL" in probe_lines
    assert path_file.read_text(encoding="utf-8") == f"{install_dir / 'bin'}\n"
