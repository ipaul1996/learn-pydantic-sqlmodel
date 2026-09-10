from pydantic import BaseModel, field_validator, model_validator

# field_validator
# It validates one field. It tells Pydantic, before accepting username, run this validation logic.
# The field validator runs while Pydantic is creating the model. At that point, there isn't a completed
# model instance yet, thus it is always a class method.

# field_validator(mode="before") -> Runs before Pydantic validates/converts that field.
# field_validator(mode="after") -> Runs after Pydantic validates/converts that field (default).


class User(BaseModel):
    username: str
    age: int

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("username cannot be empty")

        if len(value) < 4:
            raise ValueError("username must be at least 3 characters long")

        if len(value) > 50:
            raise ValueError("username must be less than 50 characters long")

        return value


user1 = User(username="  John  ", age=30)
# user2 = User(username="Ray", age=30)  # Validation error


class UserNew(BaseModel):
    username: str
    age: int

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value):
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("username cannot be empty")
        return value


# model_validator validates the whole model, especially relationships/business rules between fields.
# mode="before" works on raw input before pydantic parses type, it prepares the incoming data for validation;
# mode="after" works on the validated model, useful for checking the final values and business
# rules/relationships between fields.


class UserModel(BaseModel):
    password: str
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")

        return self


user3 = UserModel(password="123456", confirm_password="123456")
# user4 = UserModel(password="123456", confirm_password="123457")  # Validation error


class UserModelNew(BaseModel):
    first_name: str
    last_name: str

    @model_validator(mode="before")
    @classmethod
    def split_full_name(cls, data):
        if "full_name" in data:
            first, last = data["full_name"].split(" ", 1)

            data["first_name"] = first
            data["last_name"] = last

        return data


# mode="before" reshapes accepted kwargs at runtime (Pyright can't infer this)
user6 = UserModelNew(full_name="John Doe")  # pyright: ignore[reportCallIssue]

print(user6.first_name)  # John
print(user6.last_name)  # Doe


# Note:
# One field only          → field_validator
# Multiple fields related → model_validator (usually mode="after")
# Reshape whole input dict → model_validator (mode="before")
