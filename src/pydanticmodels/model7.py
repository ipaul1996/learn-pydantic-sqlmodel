import os
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pydantic Settings — BaseSettings
# pydantic-settings is a separate, official package: pip install pydantic-settings
# (already a dependency in this repo — see requirements.txt).
#
# BaseSettings is a BaseModel that ALSO knows how to read its field values from
# environment variables (and .env files, and secret files) instead of only from
# constructor kwargs. This is the standard way to configure a production app:
# one typed class instead of scattered os.environ.get(...) calls everywhere.
#
# A light version of this already appears in sqlmodel9.py (loading DATABASE_URL).
# This file goes deeper into BaseSettings itself.


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="app_")

    app_name: str = "Hero API"
    debug: bool = False
    port: int = 8000


# Env vars are matched to fields by name, CASE-INSENSITIVE by default, with the
# configured env_prefix stripped. So "APP_APP_NAME" / "app_app_name" / "App_App_Name"
# all set app_name here.
os.environ["APP_APP_NAME"] = "Production Hero API"
os.environ["APP_DEBUG"] = (
    "true"  # bool fields coerce "true"/"1"/"yes" etc. like FastAPI query params
)

settings = AppSettings()
print("ENV VARS —", settings.model_dump())

del os.environ["APP_APP_NAME"]
del os.environ["APP_DEBUG"]


# Validation of default values — IMPORTANT DIFFERENCE from plain BaseModel.
# BaseModel does NOT validate defaults unless you opt in with validate_default=True
# (model2.py/model4.py never needed this). BaseSettings validates defaults by
# DEFAULT, because a bad literal default is a real bug you want caught immediately,
# not silently accepted just because no one overrode it via an env var.
class BadDefault(BaseSettings):
    port: int = "not-a-number"  # type: ignore[assignment]


try:
    BadDefault()
except ValidationError as e:
    print(
        f"\nBAD DEFAULT — caught at class-instantiation time: {e.error_count()} error(s)"
    )

# Opt out per-class with SettingsConfigDict(validate_default=False), or per-field
# with Field(validate_default=False), same as the ConfigDict option on BaseModel.


# Renaming the env var for one field — alias (both directions) or validation_alias
# (input/env only). Same Field() mechanism already used for JSON keys in model2.py.
class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="db_")

    connection_url: str = Field(
        validation_alias="database_url", default="sqlite:///./app.db"
    )


os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/prod"
print("\nALIAS —", DbSettings().model_dump())
del os.environ["DATABASE_URL"]


# Parsing complex types — list/dict/nested-model fields are parsed from an env var
# as a JSON string by default:
#   export tags='["a", "b"]'   ->  tags: list[str]
#
# For "flattening" nested settings instead of writing raw JSON, use
# env_nested_delimiter: FOO__BAR=baz becomes {"foo": {"bar": "baz"}}.
from pydantic import BaseModel


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379


class NestedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    redis: RedisSettings = RedisSettings()


os.environ["REDIS__HOST"] = "redis.prod.internal"
os.environ["REDIS__PORT"] = "6380"
print("\nNESTED (env_nested_delimiter) —", NestedSettings().model_dump())
del os.environ["REDIS__HOST"]
del os.environ["REDIS__PORT"]


# Dotenv (.env) file support — env_file points at a file with KEY=VALUE lines.
# Precedence: real environment variables ALWAYS beat values from a .env file,
# so ops can override a checked-in .env with a real env var in production.
class EnvFileSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, extra="ignore"
    )  # set per-instance below

    greeting: str = "default greeting"


dotenv_path = Path(__file__).parent / "_demo.env"
dotenv_path.write_text("greeting=hello from dotenv\n")

from_file = EnvFileSettings(_env_file=dotenv_path)  # pyright: ignore[reportCallIssue]
print("\nDOTENV —", from_file.model_dump())

os.environ["greeting"] = "hello from real env var"
from_file_and_env = EnvFileSettings(
    _env_file=dotenv_path  # pyright: ignore[reportCallIssue]
)
print("DOTENV + ENV — env var wins:", from_file_and_env.model_dump())
del os.environ["greeting"]
dotenv_path.unlink()


# Secrets — for values mounted as individual files (Docker/Kubernetes secrets),
# point secrets_dir at the directory; the FILENAME becomes the field name and the
# file's CONTENTS become the value. A missing secrets_dir only warns, it doesn't error.
secrets_dir = Path(__file__).parent / "_demo_secrets"
secrets_dir.mkdir(exist_ok=True)
(secrets_dir / "api_key").write_text("sk-super-secret-value")


class SecretFileSettings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir=str(secrets_dir))

    api_key: str


# api_key comes from the secret file, not a kwarg
loaded_from_secret = SecretFileSettings()  # pyright: ignore[reportCallIssue]
print("\nSECRETS DIR —", loaded_from_secret.model_dump())
(secrets_dir / "api_key").unlink()
secrets_dir.rmdir()


# Summary
#
# class Settings(BaseSettings): ...       -> typed config, auto-read from the environment
# model_config = SettingsConfigDict(...)  -> env_prefix, case_sensitive, env_file, secrets_dir, ...
# Env var matching                        -> field name (+ env_prefix), case-INSENSITIVE by default
# Validated defaults                      -> unlike BaseModel, BaseSettings validates defaults
#                                             by default (catches bad literals immediately)
# Field(alias=...) / Field(validation_alias=...) -> rename the env var for one field
# Complex types (list/dict/nested model)  -> parsed from a JSON-encoded env var string
# env_nested_delimiter="__"                -> FOO__BAR=baz -> {"foo": {"bar": "baz"}}
# env_file=".env"                          -> load a dotenv file; real env vars still win
# secrets_dir="/run/secrets"               -> read one value per file (Docker/K8s secrets)
#
# Field value priority (highest to lowest, when cli_parse_args is not used):
#   1. constructor kwargs (Settings(x=...))
#   2. environment variables
#   3. .env file (dotenv)
#   4. secrets directory
#   5. the field's default value
#
# Continue in model8.py for computed_field, SecretStr, and TypeAdapter.
