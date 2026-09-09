from pydantic import BaseModel, ConfigDict, ValidationError, Field

# ConfigDict / model_config
#
# Controls model-level behavior. Set on the class via model_config.
#
# extra="forbid"  → reject unknown fields
# extra="ignore"  → silently drop unknown fields (default)
# extra="allow"   → keep unknown fields on the model
#
# validate_by_name=True   → accept field name
# validate_by_alias=True  → accept alias
# frozen=True             → model instance cannot be modified after creation


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    age: int


user1 = StrictModel(name="Indra", age=27)

print(user1)

# ValidationError — unknown field
# StrictModel(name="Indra", age=27, country="India")


class IgnoreExtraModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str


user2 = IgnoreExtraModel.model_validate(
    {
        "name": "Indra",
        "extra_field": "dropped",
    }
)

print(user2.model_dump())
# {'name': 'Indra'}


class AllowExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str


user3 = AllowExtraModel.model_validate(
    {
        "name": "Indra",
        "role": "admin",
    }
)

print(user3.model_dump())
# {'name': 'Indra', 'role': 'admin'}


class FrozenUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str


frozen = FrozenUser(name="Indra")

print(frozen)

# Pylance correctly reports an error here:
# frozen.name = "Ray"
#
# Runtime also raises an error because the model is frozen.


class Profile(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    user_name: str = Field(alias="username")


profile1 = Profile.model_validate({"username": "John"})

profile2 = Profile.model_validate({"user_name": "Jane"})

print(profile1, profile2)


# ValidationError — raised when validation fails.
# Catch it to handle bad input gracefully.
#
# Useful in APIs to return structured validation errors.


class Signup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    age: int


bad_data = {
    "username": "ip",
    "age": "not-a-number",
    "hack_field": True,
}

try:
    Signup.model_validate(bad_data)

except ValidationError as e:
    print(e.error_count())
    print(e.errors())
    print(e.json(indent=2))

    # Common error dict keys:
    # loc   → where the error happened
    # msg   → human-readable message
    # type  → error type string
    # input → bad value received
