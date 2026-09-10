from pydantic import (
    BaseModel,
    SecretStr,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
)

# Computed Fields, Secrets & TypeAdapter
# Builds on model1.py (BaseModel), model2.py (Field), model6.py (field_serializer).


# computed_field — expose a @property (derived from other fields) as part of the
# model's OUTPUT, without it being a real input field. Pydantic does NOT validate
# or cache the property itself; it just calls it and serializes whatever it returns.
class Invoice(BaseModel):
    subtotal: float
    tax_rate: float  # e.g. 0.18 for 18%

    @computed_field
    @property
    def total(self) -> float:
        return round(self.subtotal * (1 + self.tax_rate), 2)


invoice = Invoice(subtotal=100.0, tax_rate=0.18)
print("COMPUTED — model_dump:", invoice.model_dump())  # 'total' is included
print("COMPUTED — model_dump_json:", invoice.model_dump_json())

# 'total' has no effect as a constructor kwarg — it isn't a real field, so under
# the default extra="ignore" it is silently dropped, not validated or stored.
ignored = Invoice(
    subtotal=50.0,
    tax_rate=0.10,
    total=999999,  # pyright: ignore[reportCallIssue]
)
print("COMPUTED — passing total= is ignored:", ignored.total)  # still computed: 55.0

# Only shows up in the OUTPUT (serialization) schema, never the input (validation) one.
print(
    "COMPUTED — in validation schema:",
    "total" in Invoice.model_json_schema(mode="validation")["properties"],
)
print(
    "COMPUTED — in serialization schema:",
    "total" in Invoice.model_json_schema(mode="serialization")["properties"],
)


# SecretStr / SecretBytes — wrap sensitive values so they never accidentally leak
# into logs, error messages, or a repr(). Same idea for bytes: SecretBytes.
class UserAccount(BaseModel):
    username: str
    password: SecretStr


account = UserAccount(
    username="indra",
    password="hunter2",  # pyright: ignore[reportArgumentType] — Pydantic coerces str -> SecretStr at runtime
)
print("\nSECRET — printed model:", account)  # password=SecretStr('**********')
print("SECRET — get_secret_value():", account.password.get_secret_value())
print(
    "SECRET — model_dump keeps it masked:", account.model_dump()
)  # still a SecretStr object, not a str
print("SECRET — model_dump_json masks it too:", account.model_dump_json())

# Two SecretStr instances compare equal if their underlying values match — useful
# for "did the password change" checks without ever printing the value itself.
print(
    "SECRET — equality by underlying value:",
    SecretStr("hunter2") == SecretStr("hunter2"),
)


# By default even model_dump_json() masks the value. If (and only if) you truly
# need the raw secret in an outgoing JSON payload (e.g. forwarding credentials to
# a downstream system that needs them), reveal it explicitly with a field_serializer
# scoped to when_used="json" — never do this just to make logging "convenient".
class ServiceCredentials(BaseModel):
    api_key: SecretStr

    @field_serializer("api_key", when_used="json")
    def reveal_for_downstream_call(self, value: SecretStr) -> str:
        return value.get_secret_value()


creds = ServiceCredentials(
    api_key="sk-prod-12345"  # pyright: ignore[reportArgumentType]
)
print("SECRET — masked by default:", creds.model_dump())
print("SECRET — revealed only in JSON via field_serializer:", creds.model_dump_json())


# TypeAdapter — validate/serialize a type that ISN'T a BaseModel: a bare list, a
# dict, a dataclass, or any other Pydantic-compatible type. Common for API
# responses whose top-level JSON is a list/array, not a single object.
class Item(BaseModel):
    id: int
    name: str


item_adapter = TypeAdapter(list[Item])

# raw_data could come straight from `requests.get(...).json()` — a plain list of
# dicts, with no wrapper model to hang a "items" field on.
raw_data = [
    {"id": 1, "name": "Plumbus"},
    {"id": "2", "name": "Portal Gun"},
]  # "2" coerces to int
items = item_adapter.validate_python(raw_data)
print("\nTYPEADAPTER — validated:", items)

# .dump_json() returns bytes (not str, unlike model_dump_json()) — a deliberate
# V2 API choice; decode it yourself if you need a str.
dumped = item_adapter.dump_json(items)
print("TYPEADAPTER — dump_json() returns", type(dumped).__name__, "->", dumped)

try:
    item_adapter.validate_python([{"id": "not-a-number", "name": "Bad"}])
except ValidationError as e:
    print("TYPEADAPTER — same structured errors as a model:", e.errors()[0]["loc"])

# Reuse ONE TypeAdapter instance (building it analyzes the type into a schema,
# which has real overhead) — don't recreate it inside a hot loop or per-request.


# Summary
#
# @computed_field + @property        -> include a derived value in model_dump()/model_dump_json()
#                                        and the SERIALIZATION json schema only; not a real input field
#                                        (passing it as a kwarg is silently ignored under extra="ignore")
# SecretStr / SecretBytes            -> mask a value in repr()/str()/model_dump_json() by default
# .get_secret_value()                -> the only way to read the actual value back out
# model_dump()                        -> keeps the SecretStr object itself (still masked), not a plain str
# field_serializer(..., when_used="json") -> the deliberate escape hatch to reveal a secret in JSON output
# TypeAdapter(SomeType)                -> validate_python/validate_json/dump_python/dump_json/json_schema
#                                        for types that are NOT a BaseModel (list[...], dict[...], dataclasses)
# TypeAdapter(...).dump_json()         -> returns bytes, unlike BaseModel.model_dump_json() which returns str
# Build a TypeAdapter once, reuse it   -> constructing it has real (schema-building) overhead
