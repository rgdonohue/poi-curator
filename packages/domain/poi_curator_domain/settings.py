from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POI_CURATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    env: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://poi_curator:poi_curator@localhost:5432/poi_curator"
    default_region: str = "santa-fe"
    scoring_profile_version: str = "v0"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_fallback_url: str = "https://overpass.kumi.systems/api/interpreter"
    overpass_timeout_seconds: int = 60
    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"
    wikidata_timeout_seconds: int = 30
    city_gis_mapserver_url: str = "https://gis.santafenm.gov/server/rest/services/Public_Viewer/MapServer"
    city_gis_timeout_seconds: int = 45
    nrhp_listed_csv_url: str = (
        "https://www.nps.gov/common/uploads/sortable_dataset/nationalregister/"
        "53699964-0893-68AA-5273CB1C614B8BB3/nri-national-register-listed20250624.csv"
    )
    nrhp_timeout_seconds: int = 60
    nm_hpd_register_workbook_url: str = (
        "https://www.nmhistoricpreservation.org/assets/files/registers/2026/"
        "SR%20NR%20Excel%20Database.xlsx"
    )
    nm_hpd_timeout_seconds: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
