import re
from datetime import datetime


CITATION_STYLES = {
    "apa": "APA 7ª edición",
    "mla": "MLA 9ª edición",
    "chicago": "Chicago 17ª edición",
    "ieee": "IEEE"
}


def format_apa(source_type: str, data: dict) -> str:
    if source_type == "web":
        return _format_web_apa(data)
    elif source_type == "book":
        return _format_book_apa(data)
    elif source_type == "journal":
        return _format_journal_apa(data)
    else:
        return _format_web_apa(data)


def format_mla(source_type: str, data: dict) -> str:
    if source_type == "web":
        return _format_web_mla(data)
    elif source_type == "book":
        return _format_book_mla(data)
    elif source_type == "journal":
        return _format_journal_mla(data)
    else:
        return _format_web_mla(data)


def format_chicago(source_type: str, data: dict) -> str:
    if source_type == "web":
        return _format_web_chicago(data)
    else:
        return _format_web_chicago(data)


def _format_web_apa(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    year = data.get("year", str(datetime.now().year))
    title = data.get("title", "Título desconocido")
    url = data.get("url", "")
    site = data.get("site_name", "Sitio web")
    access_date = datetime.now().strftime("%d de %B de %Y")

    return f"{author} ({year}). {title}. {site}. URL: {url}"


def _format_book_apa(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    year = data.get("year", str(datetime.now().year))
    title = data.get("title", "Título desconocido")
    publisher = data.get("publisher", "Editorial desconocida")
    edition = data.get("edition", "")

    result = f"{author} ({year}). {title}"
    if edition:
        result += f" ({edition} ed.)"
    result += f". {publisher}."
    return result


def _format_journal_apa(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    year = data.get("year", str(datetime.now().year))
    title = data.get("title", "Título desconocido")
    journal = data.get("journal", "Revista desconocida")
    volume = data.get("volume", "")
    issue = data.get("issue", "")
    pages = data.get("pages", "")
    doi = data.get("doi", "")

    result = f"{author} ({year}). {title}. {journal}"
    if volume:
        result += f", {volume}"
    if issue:
        result += f"({issue})"
    if pages:
        result += f", {pages}"
    result += "."
    if doi:
        result += f" https://doi.org/{doi}"
    return result


def _format_web_mla(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    title = data.get("title", "Título desconocido")
    site = data.get("site_name", "Sitio web")
    url = data.get("url", "")
    access_date = datetime.now().strftime("%d %b %Y")

    return f"{author}. \"{title}.\" {site}, {access_date}, {url}."


def _format_book_mla(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    title = data.get("title", "Título desconocido")
    publisher = data.get("publisher", "Editorial desconocida")
    year = data.get("year", str(datetime.now().year))

    return f"{author}. {title}. {publisher}, {year}."


def _format_journal_mla(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    title = data.get("title", "Título desconocido")
    journal = data.get("journal", "Revista desconocida")
    volume = data.get("volume", "")
    issue = data.get("issue", "")
    year = data.get("year", str(datetime.now().year))
    pages = data.get("pages", "")
    doi = data.get("doi", "")

    result = f"{author}. \"{title}.\" {journal}, vol. {volume}"
    if issue:
        result += f", no. {issue}"
    result += f", {year}, pp. {pages}."
    if doi:
        result += f" doi:{doi}"
    return result


def _format_web_chicago(data: dict) -> str:
    author = data.get("author", "Autor desconocido")
    title = data.get("title", "Título desconocido")
    url = data.get("url", "")
    access_date = datetime.now().strftime("%B %d, %Y")

    return f"{author}. \"{title}.\" Último acceso el {access_date}. {url}."


def generate_bibliography(sources: list, style: str = "apa") -> list:
    formatters = {
        "apa": format_apa,
        "mla": format_mla,
        "chicago": format_chicago
    }

    formatter = formatters.get(style, format_apa)
    bibliography = []

    for source in sources:
        source_type = source.get("type", "web")
        citation = formatter(source_type, source)
        bibliography.append({
            "style": style,
            "citation": citation,
            "source": source
        })

    return bibliography
