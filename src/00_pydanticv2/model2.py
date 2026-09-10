from pydantic import BaseModel, Field, field_validator


class User(BaseModel):
    name: str = Field(min_length=1)
    age: int = Field(ge=18)


"""

Field
=====

ge, gt, le, lt --> Greater than, Less than, Less than or equal to, Greater than or equal to. 
Used for numeric fields.

min_length, max_length --> length limits. Used for string, list, tuple, etc.

description --> A human-readable note about the field. Does not affect validation.
title -> short label in schema.

name: str = Field(...) --> required, no default.

default_factory=... -> A callable that creates a new default each time the model is created.
items: list = []   # BAD — same list shared across all instances
items: list = Field(default_factory=list)  # GOOD — new list each time

alias --> An alternate name for the field when reading/writing data (JSON, dict keys).

User(username="John")              # input uses alias
# user_name='John'

user.model_dump(by_alias=True)     # {"username": "John"}
user.model_dump(by_alias=False)    # {"user_name": "John"}

user_name: str = Field(
    validation_alias="username",      # input JSON key
    serialization_alias="userName",   # output JSON key
)

pattern -> Regular expression pattern for string fields.

frozen=True -> immutable after create
exclude=True -> exclude from model_dump()
strict=True —> no type coercion on that field



Annotated:
==========

- Annotated[Type, metadata...]
- Type = actual Python type
- metadata = Field(...), validators, Strict, etc.

Two styles (same behavior):
- name: str = Field(min_length=1)           # assignment style
- name: Annotated[str, Field(min_length=1)] # recommended in v2


# required
name: Annotated[str, Field(min_length=1)]

# optional with default
role: Annotated[str, Field(default="user")]

# optional, can be None
bio: Annotated[str | None, Field(default=None)]

"""

# print(User(name="", age=20)) # ValidationError


# Model validate vs Constructor

# User(name="John", age=30)
# It is the normal constructor used when you already know the fields and want
# to create a Pydantic model directly.
# Another way: User(**data)

# User.model_validate(data)
# It is used when you already have some external/existing data
# (usually a dict or object) and want Pydantic to validate it against the model.

# Both use Pydantic's validation/coercion, but model_validate() also supports
# things like from_attributes, strict, and context.


# model_validate can read attributes from arbitrary objects
class Row:
    name = "Indra"
    age = 27


user1 = User.model_validate(Row(), from_attributes=True)
print(user1)

# Per-call validation options
data = {"name": "Indra", "age": "27"}
# User.model_validate(data, strict=True) # ValidationError
user2 = User.model_validate(data, strict=False)  # No ValidationError


# Context
# context is hidden runtime info for validators — passed in at model_validate time,
# read via info.context, never stored as a model field.
# We pass via model_validate(..., context={...})
# We add Add `info` parameter to @field_validator or @model_validator
# we read via info.context (type: ValidationInfo)
class UserContext(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value, info):
        request = info.context.get("request") if info.context else None
        return value


data = {"name": "John"}

user3 = UserContext.model_validate(
    data, context={"request": {"extra_info": "extra_info"}}
)

# Rule of thumb
# -> data = what the user sends
# -> context = what the server/environment knows at validation time like DB session,
# permissions, tenant ID


# Tier 1 topics continued in model4.py (ConfigDict, ValidationError) and model5.py
# (EmailStr, Literal, Union, list/dict collections). model_validate_json is in model1.py.
# Deep dive on BaseSettings (env vars, .env files, secrets): model7.py.
# SQLModel config + session DI: sqlmodel9.py (pydantic-settings, sync vs async session).


# Note: Constrcutor does not support these options.
