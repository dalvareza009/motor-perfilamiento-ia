"""Zip para instalar el motor en otro computador: codigo + dump SQL, sin secretos."""
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESCRITORIO = Path.home() / "OneDrive - Global" / "Escritorio"
if not ESCRITORIO.exists():
    ESCRITORIO = Path.home() / "Desktop"

SKIP_DIR = {
    ".venv", ".git", ".cursor", ".vercel", "__pycache__", "agent-transcripts",
    "chrome_linkedin_profile", "chrome_facebook_profile", "chrome_instagram_profile",
    "chrome_x_profile", "node_modules", ".claude",
}
SKIP_FILE = {
    ".env", ".env.para-el-jefe", "x_cookies.json", "linkedin_cookies.json",
    "facebook_cookies.json", "instagram_cookies.json",
    "perfiles_autorizados.json",
}
SKIP_PRE = ("_vercel", "_copiar", "_activar", "_probar", "_guardar", "_subir", "_chrome")
SKIP_SUF = {".pyc", ".csv", ".pdb", ".dump"}
SKIP_NAME_PART = ("_actividad_", "_recomendaciones_", "_resumen_")


def incluir(rel: Path) -> bool:
    if any(p in SKIP_DIR for p in rel.parts):
        return False
    if rel.name in SKIP_FILE or rel.suffix.lower() in SKIP_SUF:
        return False
    if rel.name.startswith("._"):
        return False
    if rel.parts[:1] == ("scripts",) and rel.name.startswith(SKIP_PRE):
        return False
    if any(p in rel.name for p in SKIP_NAME_PART):
        return False
    return True


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
            if not incluir(rel):
                continue
            zf.write(path, rel.as_posix())
            n += 1
    nombres = zipfile.ZipFile(zip_path).namelist()
    print("zip", zip_path)
    print("archivos", n, "mb", round(zip_path.stat().st_size / 1024 / 1024, 2))
    print("incluye INSTALAR.md", "INSTALAR.md" in nombres)
    print("incluye INSTALAR.bat", "INSTALAR.bat" in nombres)
    print("incluye dump", "datos_iniciales/base_datos.sql" in nombres)
    print("incluye ejemplo perfiles", "data/perfiles_autorizados.ejemplo.json" in nombres)
    print("sin cookies", not any(x.endswith("_cookies.json") for x in nombres))
    print("sin .env", ".env" not in nombres)
    print("sin perfiles reales", "data/perfiles_autorizados.json" not in nombres)


if __name__ == "__main__":
    main()
