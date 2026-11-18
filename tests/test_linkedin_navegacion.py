"""LinkedIn no debe entrar a rutas que responden 404 ni tumbar el scrape."""
from unittest.mock import MagicMock

from app.redes_seguidas import SCRIPT_CLICK_LINKEDIN_INTERESES, es_404_linkedin, ruta_linkedin_rota, _ir
from linkedin_activity_scraper import LinkedInActivityScraper


PERFIL = "https://www.linkedin.com/in/mariana-gutierrez-jaramillo/"
COMPANIES = PERFIL + "details/interests/companies/"


def test_omite_pestanas_de_intereses_que_linkedin_404():
    assert ruta_linkedin_rota(COMPANIES)
    assert ruta_linkedin_rota(PERFIL + "details/interests/groups/")
    assert ruta_linkedin_rota(PERFIL + "details/interests/schools/")
    assert ruta_linkedin_rota("https://www.linkedin.com/in/x/details/interests/newsletters/")
    assert not ruta_linkedin_rota(PERFIL)
    assert not ruta_linkedin_rota(PERFIL + "recent-activity/all/")
    assert not ruta_linkedin_rota(PERFIL + "details/experience/")


def test_404_no_si_el_perfil_ya_se_ve():
    assert es_404_linkedin(
        url=PERFIL, titulo="Mariana | LinkedIn", encabezado="Mariana Gutiérrez",
        cuerpo="esta página no existe aparece en un comentario", hay_perfil=True) is False
    assert es_404_linkedin(
        url=COMPANIES, titulo="Esta página no existe", encabezado="Esta página no existe",
        hay_perfil=False) is True
    assert es_404_linkedin(
        url=PERFIL, titulo="Esta página no existe | LinkedIn",
        encabezado="Esta página no existe", cuerpo="Esta página no existe",
        hay_perfil=False) is True
    assert es_404_linkedin(
        url="https://www.linkedin.com/in/ana/", titulo="Ana | LinkedIn",
        encabezado="Ana Pérez", cuerpo="Experiencia\nEducación", hay_perfil=False) is False


def test_abrir_no_navega_a_la_ruta_rota():
    bot = LinkedInActivityScraper(cookie_file="c.json", profile_dir="p")
    fake = MagicMock()
    bot.driver = fake
    assert bot._abrir_linkedin(COMPANIES, volver_si_falla=PERFIL) is False
    fake.get.assert_not_called()


def test_variantes_incluyen_co_linkedin():
    bot = LinkedInActivityScraper(cookie_file="c.json", profile_dir="p")
    urls = bot._variantes_perfil("https://www.linkedin.com/in/mariana-gutierrez-jaramillo/")
    assert PERFIL in urls
    assert "https://co.linkedin.com/in/mariana-gutierrez-jaramillo/" in urls
    assert not any("interests/companies" in u for u in urls)


def test_ir_no_abre_ruta_rota():
    fake = MagicMock()
    assert _ir(fake, COMPANIES, volver_a=PERFIL) is False
    fake.get.assert_not_called()


def test_click_de_intereses_no_entra_a_companies():
    assert "companies" in SCRIPT_CLICK_LINKEDIN_INTERESES
    assert "rota" in SCRIPT_CLICK_LINKEDIN_INTERESES


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print("OK ", nombre)
