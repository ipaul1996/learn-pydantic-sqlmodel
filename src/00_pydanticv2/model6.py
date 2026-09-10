from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_serializer, model_serializer

# field_serializer — customize how one field is converted to JSON/dict on output.
# Runs during model_dump() / model_dump_json(), NOT during validation (input).
#
# Use when:
#   - format dates, decimals, enums for API output
#   - hide/transform sensitive values
#   - convert list → string (or other output shape)


class Book(BaseModel):
    title: str
    published_date: date
    price: float
    tags: list[str]

    @field_serializer("tags")
    def serialize_tags(self, tags: list[str]) -> str:
        return ", ".join(tags)

    @field_serializer("published_date")
    def serialize_date(self, value: date) -> str:
        return value.isoformat()

    @field_serializer("price")
    def serialize_price(self, value: float) -> str:
        return f"${value:.2f}"


book = Book(
    title="Learning Pydantic",
    published_date=date(2024, 1, 15),
    price=29.99,
    tags=["python", "pydantic"],
)

print("Python object — tags is list:", book.tags)
print("model_dump() — tags becomes string:", book.model_dump())
print("model_dump_json():", book.model_dump_json())


# model_serializer — customize the whole model output (advanced, less common).
class User(BaseModel):
    name: str
    age: int

    @model_serializer
    def serialize_model(self):
        return {"user_name": self.name, "user_age": self.age}


user = User(name="Indra", age=27)
print("model_serializer — custom keys:", user.model_dump())


# Discriminated unions — pick the correct model from a Union using a discriminator field.
# Common for API payloads like: {"type": "cat", ...} vs {"type": "dog", ...}
#
# Without discriminator, Pydantic may try the wrong model first and give confusing errors.
# With discriminator, it reads the tag field and validates against exactly one model.


class Cat(BaseModel):
    pet_type: Literal["cat"]
    meows: int


class Dog(BaseModel):
    pet_type: Literal["dog"]
    barks: float


class Bird(BaseModel):
    pet_type: Literal["bird"]
    chirps: bool


class PetOwner(BaseModel):
    name: str
    pet: Annotated[
        Cat | Dog | Bird,
        Field(discriminator="pet_type"),
    ]


owner1 = PetOwner.model_validate(
    {
        "name": "Indra",
        "pet": {"pet_type": "cat", "meows": 5},
    }
)
print(f"DISCRIMINATED — {owner1.name}'s pet: {owner1.pet}")

owner2 = PetOwner.model_validate(
    {
        "name": "Ray",
        "pet": {"pet_type": "dog", "barks": 3.5},
    }
)
print(f"DISCRIMINATED — {owner2.name}'s pet: {owner2.pet}")

# PetOwner.model_validate({
#     "name": "X",
#     "pet": {"pet_type": "fish", "bubbles": 1},
# })  # ValidationError — unknown pet_type


# Nested discriminated union — payment methods in checkout APIs.


class CardPayment(BaseModel):
    method: Literal["card"]
    card_number: str


class UpiPayment(BaseModel):
    method: Literal["upi"]
    upi_id: str


class Checkout(BaseModel):
    amount: float
    payment: Annotated[
        CardPayment | UpiPayment,
        Field(discriminator="method"),
    ]


checkout = Checkout.model_validate(
    {
        "amount": 999.0,
        "payment": {"method": "upi", "upi_id": "user@upi"},
    }
)

if isinstance(checkout.payment, UpiPayment):
    print(f"CHECKOUT — {checkout.payment.method}: {checkout.payment.upi_id}")


# Summary
#
# field_serializer  → change one field's output shape (model_dump / JSON)
# model_serializer  → change entire model output shape
# Serializers run on OUTPUT only, not on validation input
#
# Discriminated union → Annotated[A | B | C, Field(discriminator="type_field")]
# Each variant must have a unique Literal value on the discriminator field
# Essential for polymorphic JSON (events, payments, notifications, webhooks)
#
# Continue in model7.py for Pydantic Settings (BaseSettings) — reading typed
# config from environment variables, .env files, and secrets. Then model8.py for
# computed_field, SecretStr/SecretBytes, and TypeAdapter.
