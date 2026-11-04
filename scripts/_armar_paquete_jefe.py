"""Zip local para el jefe: codigo + dump SQL, sin secretos ni Vercel."""
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESCRITORIO = Path.home() / "OneDrive - Global" / "Escritorio"
if not ESCRITORIO.exists():
    ESCRITORIO = Path.home() / "Desktop"

SKIP_DIR = {
    ".venv", ".git", ".cursor", ".vercel", "__pycache__", "agent-transcripts",
    "chrome_linkedin_profile", "chrome_facebook_profile", "chrome_instagram_profile",
    "chrome_x_profile", "node_modules",
}
SKIP_FILE = {
    ".env", ".env.para-el-jefe", "x_cookies.json", "linkedin_cookies.json",
    "facebook_cookies.json", "instagram_cookies.json",
    "vercel.json", "Dockerfile", ".vercelignore",
}
SKIP_PRE = ("_vercel", "_copiar", "_activar", "_probar", "_guardar", "_subir", "_armar", "_chrome")
SKIP_SUF = {".pyc", ".csv", ".pdb", ".dump"}


def main():
    dump = RAIZ / "datos_iniciales" / "base_datos.sql"
    if not dump.exists():
        raise SystemExit("falta datos_iniciales/base_datos.sql")
    zip_path = ESCRITORIO / "motor_perfilamiento_ia_equipo.zip"
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in RAIZ.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(RAIZ)
            if any(p in SKIP_DIR for p in rel.parts):
                continue
            if rel.name in SKIP_FILE or rel.suffix.lower() in SKIP_SUF:
                continue
            if rel.name.startswith("._"):
                continue
            if rel.parts[:1] == ("scripts",) and rel.name.startswith(SKIP_PRE):
                continue
            zf.write(path, rel.as_posix())
            n += 1
    print("zip", zip_path.name, "archivos", n, "mb", round(zip_path.stat().st_size / 1024 / 1024, 2))
    print("incluye_dump", "datos_iniciales/base_datos.sql" in zipfile.ZipFile(zip_path).namelist())


if __name__ == "__main__":
    main()
