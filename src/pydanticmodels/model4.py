from pydantic import BaseModel, ConfigDict, ValidationError, Field


# ConfigDict / model_config
# Controls model-level behavior. Set on the class via model_config.
#
# extra="forbid"  → reject unknown fields (best for strict APIs)
# extra="ignore"  → silently drop unknown fields (default in v2)
# extra="allow"   → keep unknown fields on the model
#
# populate_by_name=True → accept both field name and alias as input
# frozen=True           → model instance cannot be modified after creation


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    age: int


user1 = StrictModel(name="Indra", age=27)
print(user1)

# StrictModel(name="Indra", age=27, country="India")  # ValidationError — unknown field


class IgnoreExtraModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str


user2 = IgnoreExtraModel(name="Indra", extra_field="dropped")
print(user2.model_dump())   # {'name': 'Indra'} — extra_field ignored


class AllowExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str


user3 = AllowExtraModel(name="Indra", role="admin")
print(user3.model_dump())   # {'name': 'Indra', 'role': 'admin'}


class FrozenUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str


frozen = FrozenUser(name="Indra")
print(frozen)
# frozen.name = "Ray"  # ValidationError — instance is immutable


# populate_by_name=True — accept both Python field name AND alias as input.
# Useful when API clients may send either snake_case or camelCase.

class Profile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_name: str = Field(alias="username")


profile1 = Profile(username="John")     # via alias
profile2 = Profile(user_name="Jane")    # via field name — works because populate_by_name=True
print(profile1, profile2)


# ValidationError — raised when validation fails. Catch it to handle bad input gracefully.
# Useful in APIs to return 422 with structured error details.

class Signup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    age: int


bad_data = {"username": "ip", "age": "not-a-number", "hack_field": True}

try:
    Signup.model_validate(bad_data)
except ValidationError as e:
    print(e.error_count())       # number of errors
    print(e.errors())            # list of error dicts (loc, type, msg, input)
    print(e.json(indent=2))      # JSON string of all errors — good for API responses

# Common error dict keys:
#   loc   → where the error happened, e.g. ('age',) or ('address', 'city')
#   msg   → human-readable message
#   type  → error type string, e.g. 'int_parsing', 'extra_forbidden'
#   input → the bad value that was received
